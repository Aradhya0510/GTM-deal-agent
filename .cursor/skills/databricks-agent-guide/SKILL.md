---
name: databricks-agent-guide
description: >-
  Build production-grade stateful tool-calling agents on Databricks using LangGraph,
  MLflow ResponsesAgent, Lakebase Postgres memory, UC Functions, Vector Search, and
  AI Gateway. Use when building, deploying, or debugging Databricks agents, or when
  the user asks about agent architecture, memory, tools, or deployment patterns.
---

# Databricks Agent Guide

Production patterns for building stateful tool-calling agents on Databricks, distilled from real deployment experience.

## Architecture Overview

```
Streamlit App (Databricks Apps)
  → Model Serving Endpoint (ResponsesAgent + LangGraph)
    → Pre-guardrail (injection scan)
    → LangGraph tool-calling loop:
        Agent Node (ChatDatabricks → AI Gateway → LLM)
        ↕ tool calls
        Tools Node:
          - Lakebase Memory (CheckpointSaver + DatabricksStore)
          - UC Functions (UCFunctionToolkit)
          - Vector Search (VectorSearchRetrieverTool)
    → Post-guardrail (PII scan)
  → Response with tool call trace
```

## Correct Imports (Critical)

```python
# LLM + tools
from databricks_langchain import ChatDatabricks, UCFunctionToolkit, VectorSearchRetrieverTool

# Custom tools
from langchain_core.tools import tool

# ResponsesAgent (NOT from databricks.agents)
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest, ResponsesAgentResponse,
    ResponsesAgentStreamEvent, output_to_responses_items_stream,
    to_chat_completions_input,
)

# Lakebase Postgres memory
from databricks_langchain import CheckpointSaver, DatabricksStore
# Async: AsyncCheckpointSaver, AsyncDatabricksStore

# LangGraph
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode

# Resources for auth passthrough in log_model()
from mlflow.models.resources import (
    DatabricksServingEndpoint, DatabricksFunction,
    DatabricksVectorSearchIndex, DatabricksSQLWarehouse, DatabricksTable,
)

# Deployment (separate file!)
from databricks.agents import deploy
```

**`databricks-agents`** is deployment-only (`deploy()`, `get_deployments()`). Agent building uses `mlflow` + `databricks_langchain`.

## Memory: Lakebase Postgres

### Short-term (session persistence)

```python
from databricks_langchain import CheckpointSaver

checkpointer = CheckpointSaver(instance_name="my-instance")
checkpointer.setup()
graph = builder.compile(checkpointer=checkpointer)
# Pass thread_id in config: {"configurable": {"thread_id": "..."}}
```

### Long-term (cross-session, semantic search)

```python
from databricks_langchain import DatabricksStore

store = DatabricksStore(
    instance_name="my-instance",
    embedding_endpoint="databricks-gte-large-en",
    embedding_dims=1024,  # REQUIRED when embedding_endpoint is set
)
store.setup()

# Write
store.put(("user_memories", user_id), "pref_tone", {"type": "preference", "content": "casual tone"})

# Semantic search (not rigid SQL WHERE)
results = store.search(("user_memories", user_id), query="email preferences", limit=10)
for item in results:
    print(item.key, item.value)
```

### Auth on Model Serving

`agents.deploy()` creates a new invisible SP per model version with no Postgres role. Use a stable PAT:

```python
import os
from databricks.sdk import WorkspaceClient

token = os.environ.get("LAKEBASE_PAT")
if token:
    wc = WorkspaceClient(host=os.environ["DATABRICKS_HOST"], token=token)
    kwargs["workspace_client"] = wc

checkpointer = CheckpointSaver(**kwargs)
store = DatabricksStore(**kwargs, embedding_endpoint=..., embedding_dims=1024)
```

Deploy with: `environment_vars={"LAKEBASE_PAT": "{{secrets/scope/key}}"}`

On Databricks Apps the SP is stable - no PAT needed.

### Lakebase Postgres setup

```bash
# Create instance
databricks database create-database-instance my-instance --capacity CU_1

# Grant permissions to app SPs
databricks api patch /api/2.0/permissions/database-instances/my-instance --json '{
  "access_control_list": [
    {"service_principal_name": "SP_ID", "permission_level": "CAN_USE"}
  ]
}'

# Grant Postgres-level access (run as databricks_superuser via notebook)
GRANT CONNECT ON DATABASE databricks_postgres TO PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO PUBLIC;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO PUBLIC;
```

## Tools

### UC Functions

```python
uc_toolkit = UCFunctionToolkit(
    function_names=["catalog.schema.my_function"]
)
tools.extend(uc_toolkit.tools)
```

UC SQL functions must use `RETURNS TABLE(result STRING)`, not scalar `RETURNS STRING`.

### Vector Search

```python
retriever = VectorSearchRetrieverTool(
    index_name="catalog.schema.my_index",
    num_results=4,
    columns=["id", "text", "metadata_col"],
)
tools.append(retriever)
```

Source tables need `delta.enableChangeDataFeed = true`. Use an existing warmed VS endpoint to avoid 20-30 min provisioning delays.

### Custom Tools (Lakebase memory as visible tool)

```python
@tool
def recall_memory(user_id: str) -> str:
    """Load user preferences from Lakebase memory."""
    results = store.search(("user_memories", user_id), query="preferences", limit=10)
    return json.dumps([{"key": r.key, **r.value} for r in results])
```

Making memory a visible `@tool` (not hidden pre-processing) lets it show up in tool call cards for demo impact.

## LangGraph Agent Pattern

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence, add_messages]

def should_continue(state):
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"

def _build_graph(checkpointer=None, store=None):
    def call_model(state):
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + list(state["messages"])
        return {"messages": [llm_with_tools.invoke(msgs)]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", RunnableLambda(call_model))
    builder.add_node("tools", ToolNode(tools))
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer, store=store)
```

## ResponsesAgent Wrapper

```python
class MyAgent(ResponsesAgent):
    def predict_stream(self, request):
        custom = getattr(request, "custom_inputs", None) or {}
        thread_id = custom.get("thread_id") or str(uuid.uuid4())
        messages = to_chat_completions_input([m.model_dump() for m in request.input])

        graph = _build_graph(checkpointer=_checkpointer, store=_store)
        config = {"configurable": {"thread_id": thread_id}}

        for event in graph.stream({"messages": messages}, stream_mode=["updates"], config=config):
            if event[0] == "updates":
                for node_data in event[1].values():
                    if node_data.get("messages"):
                        yield from output_to_responses_items_stream(node_data["messages"])

mlflow.models.set_model(MyAgent())
```

Hand-built `ResponsesAgentStreamEvent` items MUST include `id` and `role` fields.

## Deployment

### File separation (critical)

- `agent.py` — agent definition + `set_model()`. NO `log_model()` or `deploy()`.
- `log_and_deploy.py` — separate notebook that calls `log_model(python_model="agent.py")` then `deploy()`.

Mixing them causes infinite recursion (100+ re-executions).

### Resource declaration

```python
resources = [
    DatabricksServingEndpoint(endpoint_name="my-llm"),
    DatabricksServingEndpoint(endpoint_name="my-embedding"),
    DatabricksSQLWarehouse(warehouse_id="..."),  # if using SQL API
    DatabricksTable(table_name="catalog.schema.table"),  # read-only access
]
for tool in uc_toolkit.tools:
    resources.append(DatabricksFunction(function_name=tool.uc_function_name))
for tool in [retriever1, retriever2]:
    resources.extend(tool.resources)
```

`DatabricksTable` grants SELECT only. For writes, use PAT auth or Lakebase Postgres.

### pip_requirements

```python
pip_requirements=[
    "mlflow>=3.6.0",
    "databricks-langchain[memory]>=0.17.0",
    "langgraph>=0.3",
    "langgraph-checkpoint-postgres>=2.0.5",
    "databricks-agents",
    "pydantic",
]
```

### Serverless job submission

No `%pip install` in notebooks — use environment spec:

```json
{
  "environments": [{"environment_key": "default", "spec": {
    "client": "2",
    "dependencies": ["databricks-langchain[memory]>=0.17.0", "langgraph-checkpoint-postgres>=2.0.5"]
  }}]
}
```

## AI Gateway

Configure on the LLM endpoint for: usage tracking, inference tables, rate limits, safety + PII guardrails. All traffic flows through the gateway automatically when using `ChatDatabricks(endpoint=...)`.

## Inline Guardrails

```python
# Pre-request: regex injection detection
_INJECTION_RE = re.compile(r"ignore previous instructions|system prompt|jailbreak|...", re.IGNORECASE)

# Post-response: PII leakage scan
_PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}
```

Log security events to an audit Delta table via SQL Statement Execution API.

## Databricks Apps (Streamlit)

- Bind to port 8000 (default `DATABRICKS_APP_PORT`). Never specify `--server.port`.
- No `env:` with `value_from:` in app.yaml — causes parse errors.
- Use `Config(http_timeout_seconds=300)` for agent calls (5+ tool calls take 2-3 min).
- No `@st.cache_data` — use dict-based TTL caches.
- Declare Lakebase instance in `app.yaml`:
  ```yaml
  resources:
    - name: lakebase-memory
      database:
        instance_name: my-instance
        database_name: databricks_postgres
        permission: CAN_CONNECT_AND_CREATE
  ```

## Endpoint Maintenance

Max 15 served entities. Trim old versions before redeploying:

```bash
databricks api put /api/2.0/serving-endpoints/{name}/config --json '{
  "served_entities": [{"entity_name": "...", "entity_version": "LATEST", ...}]
}'
```

## Additional resources

For workspace-specific config (instance names, endpoints, secrets), see [CLAUDE.md](../../../CLAUDE.md).
