# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GTM Deal Intelligence Agent — a LangGraph tool-calling agent on Databricks that helps B2B SaaS account executives with deal scoring, account research, competitive intel, and personalized outreach. Showcases 13 Databricks capabilities in a single demo app.

**Deployed on:** `e2-demo-west.cloud.databricks.com` | Catalog: `users` | Schema: `aradhya_chouhan`

## Architecture

**Production agent** (`deployment/agent.py`): Single LangGraph graph with a tool-calling loop.

```
User query → agent node (Claude Sonnet 4.6) → tool calls? → yes → tools node → back to agent
                                               → no  → END (return response)
```

5 tools available:
- `calculate_deal_health` (UC TABLE Function) — scores deals 0-100 with risk flags
- `get_account_signals` (UC TABLE Function) — full account 360 (contacts, opps, ARR)
- `gtm_transcripts_idx` (Vector Search) — 7 Gong call transcripts
- `gtm_battlecards_idx` (Vector Search) — 4 competitive battlecards
- `gtm_stories_idx` (Vector Search) — 5 won/lost deal stories

### Critical: Correct SDK Imports

```python
# CORRECT — tools come from databricks_langchain
from databricks_langchain import ChatDatabricks, UCFunctionToolkit, VectorSearchRetrieverTool

# CORRECT — ResponsesAgent comes from mlflow.pyfunc
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse, ResponsesAgentStreamEvent
from mlflow.types.responses import output_to_responses_items_stream, to_chat_completions_input

# CORRECT — resources for auth passthrough in log_model()
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksFunction, DatabricksVectorSearchIndex

# WRONG — these do NOT exist:
# from databricks.agents.tools import VectorSearchRetriever, UCFunctionTool  # NO!
# from databricks.agents import ResponsesAgent, ChatAgent  # NO!
# from databricks.agents import create_agent_executor  # NO!
```

`databricks-agents` (v1.9.4) is a **deployment-only** SDK — it provides `deploy()`, `get_deployments()`, etc. Agent building uses `mlflow` + `databricks_langchain`.

### Key Files

- **`deployment/agent.py`** — Standalone agent definition + `mlflow.models.set_model()`. This is what Model Serving loads. Must NOT contain any logging/deployment code.
- **`deployment/log_and_deploy_notebook.py`** — Databricks notebook that calls `mlflow.pyfunc.log_model(python_model="agent.py")` and `agents.deploy()`. Separate from agent.py to avoid infinite recursion.
- **`src/servicenow_gtm_agent/graph.py`** — Reusable graph builder for local dev.
- **`src/servicenow_gtm_agent/tools/`** — Tool wrappers using `databricks_langchain`.
- **`configs/e2_demo_west.yaml`** — Workspace-specific config (catalog, schema, endpoints, index names).

## Hard-Won Deployment Learnings

### 1. agent.py MUST be separate from the logging notebook
`mlflow.pyfunc.log_model(python_model="notebook.py")` re-executes the entire file to validate it. If the file contains `log_model()` itself → infinite recursion (100+ runs). Always separate agent definition from log/deploy code.

### 2. UC SQL Functions: use RETURNS TABLE, not scalar RETURNS STRING
UC SQL scalar functions treat the entire body as a correlated subquery when referencing parameters. This causes `MUST_AGGREGATE_CORRELATED_SCALAR_SUBQUERY` errors with any subqueries. Fix: use `RETURNS TABLE(result STRING)` instead.

### 3. Python UC Functions cannot use SparkSession on serverless
`pyspark.errors.PySparkRuntimeError: JAVA_GATEWAY_EXITED` — Python UDFs on serverless SQL don't have a Spark context. Use SQL functions with pre-aggregated JOINs instead.

### 4. Vector Search: use existing warmed endpoints
Delta-sync indexes on NEWLY CREATED endpoints can take 20-30+ minutes ("pending endpoint provisioning"). Using an existing active endpoint (e.g., `dbdemos_vs_endpoint`) creates indexes in under 1 minute.

### 5. Serverless notebooks: no %pip, use environment spec
`%pip install` + `%restart_python` fails on serverless job submission ("spark should be initialized with first notebook command"). Dependencies go in the `Environment(dependencies=[...])` spec when submitting via SDK.

### 6. MLflow autolog conflicts with explicit start_run()
`mlflow.langchain.autolog()` creates an active run. A subsequent `mlflow.start_run()` raises "Run with UUID ... is already active". Fix: call `mlflow.end_run()` before `start_run()`, or don't use autolog in the logging notebook.

### 7. Resources for auth passthrough
When logging with `mlflow.pyfunc.log_model()`, declare all Databricks resources so Model Serving can authenticate:
```python
resources = [DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT)]
for tool in tools:
    if isinstance(tool, UnityCatalogTool):
        resources.append(DatabricksFunction(function_name=tool.uc_function_name))
    elif isinstance(tool, VectorSearchRetrieverTool):
        resources.extend(tool.resources)  # auto-includes VS index + embedding endpoint
```

### 8. Source tables need CDF for delta-sync indexes
`TBLPROPERTIES (delta.enableChangeDataFeed = true)` must be set on source tables BEFORE creating delta-sync Vector Search indexes.

### 9. Databricks Apps: Streamlit must bind to port 8000
The Databricks Apps proxy routes to `DATABRICKS_APP_PORT` (defaults to 8000). Using `--server.port 8501` causes 502 Bad Gateway. Fix: use bare `["streamlit", "run", "app.py"]` in app.yaml — Streamlit auto-detects the correct port. Never specify port args.

### 10. Databricks Apps: no `env` with `value_from` in app.yaml
The `env:` section with `value_from: workspace` / `value_from: token` causes `[ERROR] invalid format for env`. Omit the `env:` section entirely — Databricks Apps auto-injects auth credentials.

### 11. Agent endpoint timeout: use 300s for complex queries
Multi-tool queries (5+ tool calls) can take 2-3 minutes. The default SDK timeout (60s) causes timeouts. Set `Config(http_timeout_seconds=300)` when calling the agent endpoint from the app.

## Commands

```bash
pip install -e ".[dev]"                   # Install in dev mode
pytest                                    # Run all tests
pytest tests/test_config.py::test_name    # Single test
ruff check src/ tests/                    # Lint
ruff format src/ tests/                   # Format
```

## Setup Scripts (run order on Databricks)

Infrastructure in `setup/` — run as Databricks notebooks:
1. `00_create_catalog_schema.sql` — UC catalog + schemas
2. `01_lakebase_schema.sql` — Lakebase CRM + memory tables
3. `04_seed_demo_data.py` — Demo data (run before VS indexes)
4. `02_vector_search_indexes.py` — 3 delta-sync indexes (use existing warmed endpoint!)
5. `03_uc_functions.sql` — UC TABLE Function tools
6. `05_uc_governance.sql` — RLS + column masking
7. `06_lakewatch_rules.py` — Security detection rules

## Deployment

```bash
# 1. Upload agent.py to workspace
databricks workspace import /Workspace/Users/.../agent.py --file deployment/agent.py

# 2. Upload and run log_and_deploy notebook (logs model + deploys endpoint)
databricks workspace import /Users/.../log_and_deploy --file deployment/log_and_deploy_notebook.py --format SOURCE --language PYTHON

# 3. Submit as serverless job
# See deployment/log_and_deploy_notebook.py — it handles log_model + register + deploy
```

Endpoint name: `agents_users-aradhya_chouhan-gtm_deal_intelligence_agent`

## Workspace Assets (e2-demo-west)

| Asset | Name |
|---|---|
| Tables | `users.aradhya_chouhan.gtm_accounts`, `gtm_contacts`, `gtm_opportunities`, `gtm_outreach_log`, `gtm_call_transcripts`, `gtm_battlecards`, `gtm_deal_stories` |
| VS Endpoint | `dbdemos_vs_endpoint` |
| VS Indexes | `users.aradhya_chouhan.gtm_transcripts_idx`, `gtm_battlecards_idx`, `gtm_stories_idx` |
| UC Functions | `users.aradhya_chouhan.calculate_deal_health`, `get_account_signals` |
| MLflow Experiment | `/Users/aradhya.chouhan@databricks.com/gtm-deal-intelligence` |
| Model | `users.aradhya_chouhan.gtm_deal_intelligence_agent` |
| Serving Endpoint | `agents_users-aradhya_chouhan-gtm_deal_intelligence_agent` |

## Design References

- `gtm_implementation_guide.html` — Full 7-phase implementation plan with code examples.
- `gtm_memory_layer.html` — Stateful memory layer design (CheckpointSaver, extraction agent, time travel).
