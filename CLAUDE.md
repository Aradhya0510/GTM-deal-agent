# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GTM Deal Intelligence Agent — a LangGraph tool-calling agent on Databricks that helps B2B SaaS account executives with deal scoring, account research, competitive intel, and personalized outreach. Showcases 13+ Databricks capabilities in a single demo app.

**Deployed on:** `e2-demo-west.cloud.databricks.com` | Catalog: `users` | Schema: `aradhya_chouhan`

## Architecture

**Production agent** (`deployment/agent.py`): Single LangGraph graph with a tool-calling loop + Lakebase memory.

```
User query → guardrail check → agent node (Claude Sonnet 4.6) → tool calls? → yes → tools node → back to agent
                                                                              → no  → END
Short-term: Lakebase CheckpointSaver (cross-replica) with MemorySaver fallback + client-side replay
Long-term:  recall_lakebase_memory tool → Delta memory tables via SQL Statement Execution API
Security:   Pre-request injection detection + post-response PII scan → audit_agent_access table
```

7 tools available:
- `recall_lakebase_memory` (Lakebase) — loads AE preferences, account context, deal decisions from Delta memory tables
- `store_lakebase_memory` (Lakebase) — writes new facts/preferences to memory tables in real-time
- `calculate_deal_health` (UC TABLE Function) — scores deals 0-100 with risk flags
- `get_account_signals` (UC TABLE Function) — full account 360 (contacts, opps, ARR)
- `gtm_transcripts_idx` (Vector Search) — 7 Gong call transcripts
- `gtm_battlecards_idx` (Vector Search) — 4 competitive battlecards
- `gtm_stories_idx` (Vector Search) — 5 won/lost deal stories

### Memory Architecture

**Short-term** (multi-turn within a session):
- App sends **full conversation history** as `input` (not just the latest message) — client-side replay
- `thread_id` tracked per session in `st.session_state` and passed via `custom_inputs`
- Lakebase `CheckpointSaver` (from `databricks.agents.lakebase`) for cross-replica persistence; falls back to `MemorySaver` if not available
- Enables follow-ups: "make it shorter", "try a different angle"

**Long-term** (cross-session persistence):
- Agent calls `recall_lakebase_memory(ae_id, account_id)` as its **first tool call** on every query — this is a visible LangGraph tool that shows up in tool call cards
- Queries 3 Delta tables via SQL Statement Execution API (`warehouse_id: 75fd8278393d07eb`)
- Returns structured JSON with preferences, account context, and deal decisions
- Agent calls `store_lakebase_memory()` to write new facts during conversation (step 6 in critical workflow)
- At session end: `_extract_and_store_memories()` runs haiku extraction agent for batch writes
- Tables: `users.aradhya_chouhan.memory_ae_profiles`, `memory_account_context`, `memory_deal_decisions`
- **Auth**: Reads use auto-auth passthrough (`DatabricksTable` resource); writes use a dedicated PAT via `LAKEBASE_SQL_TOKEN` env var (secret: `gtm-agent/sql-write-token`)
- **AE IDs**: Short format (`ae-jamie`, `ae-sarah`) — must match between seed data and app `AE_PROFILES`

**Key design decision**: Memory is a visible tool call (not a hidden pre-processing step) so it appears in the demo UI alongside UC Functions and Vector Search. The system prompt instructs "ALWAYS call recall_lakebase_memory FIRST".

### Security Architecture

**Inline guardrails** in `deployment/agent.py`:
- **Pre-request**: Regex-based prompt injection detection (12 patterns). Blocks request, returns safety message, logs to `audit_agent_access`.
- **Post-response**: PII leakage scan (email, phone, SSN). Logs to audit table.

**Lakewatch rules** in `setup/06_lakewatch_rules.py`:
- 4 SQL alert queries: prompt injection, PII in output, broad account scraping, outreach volume spike

**Audit table**: `audit_agent_access` (Delta) — logs security events and tool access. Created by `setup/07_audit_tables.py`.

### App Architecture (v2 Command Center)

**`app/app.py`** — 5-tab Streamlit app with [HELIX] industrial design system:

1. **[AGENT]** — Chat with inline tool-call cards (expandable I/O), Lakebase memory banner, latency, accept/reject feedback
2. **[ARCHITECTURE]** — 6-layer stack diagram, asset directory with deep links, 10-step request lifecycle
3. **[OBSERVE]** — Metrics cards, tool usage bar chart, recent calls table, evaluation scorecard
4. **[MEMORY]** — AE profile card, account context with confidence bars, decision log, prompt preview
5. **[SECURITY]** — Lakewatch rule cards, `[TEST INJECTION]` button, governance table, audit log

Design: Near-black backgrounds (#0A0A0A), JetBrains Mono, `+` crosshair corners, bracket notation `[LABELS]`, orange accent (#FF6200), 2px border-radius max.

### Critical: Correct SDK Imports

```python
# CORRECT — tools come from databricks_langchain
from databricks_langchain import ChatDatabricks, UCFunctionToolkit, VectorSearchRetrieverTool

# CORRECT — custom LangGraph tools via langchain_core
from langchain_core.tools import tool

# CORRECT — ResponsesAgent comes from mlflow.pyfunc
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse, ResponsesAgentStreamEvent

# CORRECT — Lakebase CheckpointSaver (with fallback)
try:
    from databricks.agents.lakebase import CheckpointSaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver

# CORRECT — resources for auth passthrough in log_model()
from mlflow.models.resources import (
    DatabricksServingEndpoint, DatabricksFunction, DatabricksVectorSearchIndex,
    DatabricksSQLWarehouse, DatabricksTable,
)

# WRONG — these do NOT exist:
# from databricks.agents.tools import VectorSearchRetriever, UCFunctionTool  # NO!
# from databricks.agents import ResponsesAgent, ChatAgent  # NO!
```

`databricks-agents` is a **deployment-only** SDK — it provides `deploy()`, `get_deployments()`, etc. Agent building uses `mlflow` + `databricks_langchain`. Exception: `databricks.agents.lakebase.CheckpointSaver` is valid for LangGraph checkpointing.

### Key Files

- **`deployment/agent.py`** — Standalone agent definition with 7 tools (2 Lakebase + 2 UC + 3 VS), inline guardrails, and `mlflow.models.set_model()`. This is what Model Serving loads. Must NOT contain any logging/deployment code.
- **`deployment/log_and_deploy_notebook.py`** — Databricks notebook that calls `mlflow.pyfunc.log_model(python_model="agent.py")` and `agents.deploy()`. Separate from agent.py to avoid infinite recursion.
- **`deployment/lakebase_memory_setup.py`** — Notebook that creates Delta memory tables and seeds demo data. Run on workspace as a serverless job.
- **`app/app.py`** — v2 Command Center: 5-tab Streamlit app with [HELIX] industrial design, tool call visualization, memory display, security dashboard, architecture blueprint.
- **`setup/07_audit_tables.py`** — Creates `audit_agent_access` Delta table for security/access logging.
- **`setup/06_lakewatch_rules.py`** — 4 Lakewatch SQL alert rule definitions.
- **`src/servicenow_gtm_agent/`** — Reference implementation for local dev (graph, memory, tools).
- **`configs/e2_demo_west.yaml`** — Workspace-specific config.

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

### 7. Resources for auth passthrough — including SQL warehouse and tables
When logging with `mlflow.pyfunc.log_model()`, declare ALL Databricks resources so Model Serving can authenticate. This includes:
- LLM endpoints (primary + haiku for memory extraction)
- `DatabricksSQLWarehouse(warehouse_id=...)` for SQL Statement Execution API access
- `DatabricksTable(table_name=...)` for each Delta table the agent reads

**Critical:** `DatabricksTable` only grants **SELECT** (read) access via auto-auth passthrough. The system-generated SP is invisible (doesn't appear in API/UI) and only gets read access. For **MODIFY** (INSERT/MERGE), you must use manual authentication — see learning #18.

### 8. Source tables need CDF for delta-sync indexes
`TBLPROPERTIES (delta.enableChangeDataFeed = true)` must be set on source tables BEFORE creating delta-sync Vector Search indexes.

### 9. Databricks Apps: Streamlit must bind to port 8000
The Databricks Apps proxy routes to `DATABRICKS_APP_PORT` (defaults to 8000). Using `--server.port 8501` causes 502 Bad Gateway. Fix: use bare `["streamlit", "run", "app.py"]` in app.yaml — Streamlit auto-detects the correct port. Never specify port args.

### 10. Databricks Apps: no `env` with `value_from` in app.yaml
The `env:` section with `value_from: workspace` / `value_from: token` causes `[ERROR] invalid format for env`. Omit the `env:` section entirely — Databricks Apps auto-injects auth credentials.

### 11. Agent endpoint timeout: use 300s for complex queries
Multi-tool queries (5+ tool calls) can take 2-3 minutes. The default SDK timeout (60s) causes timeouts. Set `Config(http_timeout_seconds=300)` when calling the agent endpoint from the app.

### 12. Lakebase SDK: w.lakebase not available, but CheckpointSaver works
`WorkspaceClient().lakebase` doesn't exist on e2-demo-west (SDK v0.34.0 too old). However, `databricks.agents.lakebase.CheckpointSaver` IS available on the Model Serving runtime. Use it for session persistence, with `MemorySaver` as fallback. For data storage, use Delta tables via SQL Statement Execution API.

### 13. Make memory a visible tool for demo impact
Hidden pre-processing steps (like silently loading memory before the agent loop) don't show up in tool call cards. For demo impact, implement memory as actual LangGraph tools (`@tool` from `langchain_core.tools`) so they appear alongside UC Functions and Vector Search in the UI.

### 14. PySpark Row() with complex types fails on serverless
`spark.createDataFrame([Row(...)])` with `ARRAY<STRING>` or `datetime` fields causes `CANNOT_DETERMINE_TYPE`. Fix: use SQL INSERT statements directly via `spark.sql("INSERT INTO ...")` instead of DataFrame writes.

### 15. SQL notebooks fail on serverless job submission
SQL-language notebooks uploaded via `--language SQL` fail on serverless compute with opaque "Workload failed" errors. Fix: wrap SQL in a Python notebook using `spark.sql("""...""")` instead.

### 16. Databricks deep link URL format
Use path-based URLs with `?o=` workspace ID parameter, NOT hash-based (`#/`) routing:
```
https://e2-demo-west.cloud.databricks.com/explore/data/{catalog}/{schema}/{table}?o=2556758628403379
https://e2-demo-west.cloud.databricks.com/serving-endpoints/{name}/invocations?o=2556758628403379
https://e2-demo-west.cloud.databricks.com/explore/data/models/{catalog}/{schema}/{model}?o=2556758628403379
https://e2-demo-west.cloud.databricks.com/sql/warehouses/{id}?o=2556758628403379
```

### 17. ResponsesAgentStreamEvent items need `id` and `role` fields
When manually constructing a `ResponsesAgentStreamEvent` (e.g., for a blocked/guardrail response), the `item` dict must include `id` and `role` fields or Model Serving will fail with a validation error (`item.id Field re...`). The LangGraph `output_to_responses_items_stream` helper adds these automatically, but hand-built items need them explicitly:
```python
blocked_item = {
    "type": "message",
    "id": f"msg_{uuid.uuid4().hex[:12]}",
    "role": "assistant",
    "content": [{"type": "output_text", "text": "Blocked."}],
}
yield ResponsesAgentStreamEvent(type="response.output_item.done", item=blocked_item)
```

### 18. Auto-auth passthrough SP only gets read access — use PAT for writes
The `agents.deploy()` framework creates a hidden system SP per model version that gets **SELECT only** on `DatabricksTable` resources. It cannot INSERT/MERGE/UPDATE. The SP doesn't appear in SCIM, endpoint permissions, or query history for failed DML. To enable writes from custom tools (like `store_lakebase_memory`), use a dedicated PAT stored in Databricks secrets and injected via `environment_vars` in `agents.deploy()`:
```python
# In log_and_deploy_notebook.py
deploy(model_name=..., model_version=..., environment_vars={
    "LAKEBASE_SQL_TOKEN": "{{secrets/gtm-agent/sql-write-token}}",
})

# In agent.py — use a separate WorkspaceClient for SQL, not the default auto-auth one
token = os.environ.get("LAKEBASE_SQL_TOKEN")
if token:
    w = WorkspaceClient(host=host, token=token)  # Has MODIFY
else:
    w = WorkspaceClient()  # Auto-auth, SELECT only
```
**Do NOT** set `DATABRICKS_TOKEN` globally — that overrides auto-auth for ALL resources. Use a custom env var name.

### 19. AE IDs must match between seed data and app code
The memory seed data (`lakebase_memory_setup.py`) and the app's `AE_PROFILES` dict (`backend.py`) must use the **same `ae_id` format**. Mismatches (e.g., `ae-jamie@company.com` vs `ae-jamie`) cause `recall_lakebase_memory` to return empty preferences silently, since the WHERE clause finds no rows. Current convention: short IDs like `ae-jamie`, `ae-sarah`.

### 20. UC table grants to `account users` don't cover auto-auth SPs
The system-generated SP from `agents.deploy()` is NOT in the `account users` group. Granting `MODIFY ON TABLE ... TO account users` has no effect on the serving endpoint's identity. The only reliable paths for write access are: manual PAT auth (learning #18) or on-behalf-of-user (OBO) auth with `ModelServingUserCredentials`.

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
2. `01_lakebase_schema.sql` — Lakebase CRM tables (if Lakebase available)
3. `04_seed_demo_data.py` — CRM demo data (run before VS indexes)
4. `02_vector_search_indexes.py` — 3 delta-sync indexes (use existing warmed endpoint!)
5. `03_uc_functions.sql` — UC TABLE Function tools
6. `deployment/lakebase_memory_setup.py` — Delta memory tables + seed data (run as serverless job)
7. `05_uc_governance.sql` — RLS + column masking
8. `06_lakewatch_rules.py` — Security detection rules
9. `setup/07_audit_tables.py` — Audit table for security events (run as serverless job)

## Deployment

All deployment uses `databricks --profile e2-demo-west`:

```bash
# 1. Upload agent.py to workspace
databricks --profile e2-demo-west workspace import \
  /Workspace/Users/aradhya.chouhan@databricks.com/servicenow-gtm-agent/agent.py \
  --file deployment/agent.py --format AUTO --overwrite

# 2. Upload and run memory setup notebook (creates Delta memory tables + seeds data)
databricks --profile e2-demo-west workspace import \
  /Workspace/Users/aradhya.chouhan@databricks.com/servicenow-gtm-agent/lakebase_memory_setup \
  --file deployment/lakebase_memory_setup.py --format SOURCE --language PYTHON --overwrite

databricks --profile e2-demo-west jobs submit --json '{
  "run_name": "memory-tables-setup",
  "tasks": [{"task_key": "setup", "notebook_task": {
    "notebook_path": "/Workspace/Users/aradhya.chouhan@databricks.com/servicenow-gtm-agent/lakebase_memory_setup",
    "source": "WORKSPACE"}, "environment_key": "default"}],
  "environments": [{"environment_key": "default", "spec": {"client": "2", "dependencies": []}}]
}'

# 3. Re-log and deploy agent (submit log_and_deploy notebook as serverless job)
databricks --profile e2-demo-west jobs submit --json '{
  "run_name": "agent-redeploy",
  "tasks": [{"task_key": "log_and_deploy", "notebook_task": {
    "notebook_path": "/Workspace/Users/aradhya.chouhan@databricks.com/servicenow-gtm-agent/log_and_deploy",
    "source": "WORKSPACE"}, "environment_key": "default"}],
  "environments": [{"environment_key": "default", "spec": {"client": "2",
    "dependencies": ["mlflow>=3.6.0","databricks-langchain","langgraph>=0.3","databricks-agents","pydantic"]}}]
}'

# 4. Upload and redeploy Streamlit app
databricks --profile e2-demo-west workspace import \
  /Workspace/Users/aradhya.chouhan@databricks.com/servicenow-gtm-agent/app/app.py \
  --file app/app.py --format AUTO --overwrite

databricks --profile e2-demo-west apps deploy gtm-deal-intelligence \
  --source-code-path /Workspace/Users/aradhya.chouhan@databricks.com/servicenow-gtm-agent/app
```

Endpoint name: `agents_users-aradhya_chouhan-gtm_deal_intelligence_agent`
App URL: `https://gtm-deal-intelligence-2556758628403379.aws.databricksapps.com`

## Workspace Assets (e2-demo-west)

| Asset | Name |
|---|---|
| Tables | `users.aradhya_chouhan.gtm_accounts`, `gtm_contacts`, `gtm_opportunities`, `gtm_outreach_log`, `gtm_call_transcripts`, `gtm_battlecards`, `gtm_deal_stories` |
| Audit Table | `users.aradhya_chouhan.audit_agent_access` |
| VS Endpoint | `dbdemos_vs_endpoint` |
| VS Indexes | `users.aradhya_chouhan.gtm_transcripts_idx`, `gtm_battlecards_idx`, `gtm_stories_idx` |
| UC Functions | `users.aradhya_chouhan.calculate_deal_health`, `get_account_signals` |
| MLflow Experiment | `/Users/aradhya.chouhan@databricks.com/gtm-deal-intelligence` |
| Model | `users.aradhya_chouhan.gtm_deal_intelligence_agent` |
| Serving Endpoint | `agents_users-aradhya_chouhan-gtm_deal_intelligence_agent` (v8 = SQL write PAT + resource declarations + store prompt fix) |
| Secrets | Scope `gtm-agent`, key `sql-write-token` — PAT for agent SQL writes (90-day TTL) |
| SQL Warehouse | `75fd8278393d07eb` ("Shared Endpoint") — used by agent for Lakebase memory queries |
| Memory Tables (Delta/Lakebase) | `users.aradhya_chouhan.memory_ae_profiles`, `memory_account_context`, `memory_deal_decisions` |
| Streamlit App | `gtm-deal-intelligence` — `https://gtm-deal-intelligence-2556758628403379.aws.databricksapps.com` |

## Showcase App (ServiceNow Demo)

**`showcase/`** — A separate 6-page Streamlit app branded for ServiceNow GTM AI team demo. Shares the same agent endpoint and Databricks assets as the main app but has its own design language (ServiceNow green #62D84E, "Powered by Databricks" co-branding).

**Files (5 Python + 2 config):**
- `app.py` (~490 lines) — Main entry, sidebar, navigation (st.radio horizontal), 6 page rendering
- `backend.py` (~190 lines) — WorkspaceClient, SQL cache, query_agent(), streaming SSE consumer, MLflow stats fetcher
- `data.py` (~220 lines) — 6 industry vertical data sets with ServiceNow competitors (BMC Helix, Zendesk, Atlassian, Salesforce Health Cloud, IBM Maximo, IFS, SAP)
- `styles.py` (~250 lines) — All CSS: ServiceNow branding, X-Ray, DAG animation, streaming cursors
- `components.py` (~115 lines) — render_xray(), render_dag(), render_streaming_tool_card()
- `app.yaml` — Databricks Apps config with serving endpoint resource
- `requirements.txt` — streamlit, databricks-sdk, requests

**6 pages:**
1. **Morning Briefing** — KPI strip + priority cards (single column, no fake reasoning panel)
2. **Deal Room** — Compact header + wide chat (3:1 ratio) + memory/risk sidebar. Agent called in-place with tool cards revealed one-by-one (300ms delay). No st.rerun() after call.
3. **Architecture** — CSS-animated DAG (nodes light up sequentially via @keyframes + animation-delay), "Run Test Query" button, Node Value Guide panel, request lifecycle, asset directory with deep links
4. **Outreach Studio** — Email/LinkedIn/Call drafts (demo data per industry)
5. **Pipeline** — Filterable deal table (demo data per industry)
6. **Observatory** — Real MLflow experiment runs, session tool usage, Lakebase memory browser, Lakewatch audit log, workspace deep links

**Deployed at:** `https://mission-control-2556758628403379.aws.databricksapps.com`
**Workspace path:** `/Workspace/Users/aradhya.chouhan@databricks.com/mission-control/`
**App name:** `mission-control`

**Deployment:**
```bash
# Upload all files
for f in app.py backend.py data.py styles.py components.py app.yaml requirements.txt; do
  databricks --profile e2-demo-west workspace import \
    /Workspace/Users/aradhya.chouhan@databricks.com/mission-control/$f \
    --file showcase/$f --format AUTO --overwrite
done

# Deploy
databricks --profile e2-demo-west apps deploy mission-control \
  --source-code-path /Workspace/Users/aradhya.chouhan@databricks.com/mission-control
```

### Key Showcase App Learnings

1. **Databricks Apps require app.yaml + requirements.txt** — without them, the runtime defaults to `python app.py` instead of `streamlit run app.py`, causing ScriptRunContext crashes.

2. **@st.cache_data causes ScriptRunContext errors** at import time on Databricks Apps. Use a plain dict-based TTL cache instead.

3. **st.tabs() cannot be programmatically switched** — use `st.radio(horizontal=True)` with session_state for page routing when you need to switch pages from button clicks.

4. **Streamlit streaming is fundamentally limited** — `st.empty()` updates during streaming loops get wiped by `st.rerun()`. The reliable pattern: detect unprocessed user message → call agent in-place → render tool cards with `time.sleep()` delays → show text → store in session_state → do NOT call st.rerun() after.

5. **CSS-only animation beats Streamlit re-rendering** — for the DAG "powertrain" effect, inject `@keyframes` with staggered `animation-delay` via `st.markdown(unsafe_allow_html=True)`. The animation plays smoothly in the browser while the blocking API call runs.

6. **Databricks Apps service principal needs explicit permissions** — the app.yaml resource declaration doesn't always auto-grant CAN_QUERY. Grant manually: `databricks api patch /api/2.0/permissions/serving-endpoints/{endpoint_id} --json '{"access_control_list":[{"service_principal_name":"...","permission_level":"CAN_QUERY"}]}'`

7. **Selectbox white-on-white CSS fix** — only override `div[data-baseweb="select"]>div>div` (the trigger text), NOT the dropdown list items which need their default readable background.

## Design References

- `gtm_implementation_guide.html` — Full 7-phase implementation plan with code examples.
- `gtm_memory_layer.html` — Stateful memory layer design (CheckpointSaver, extraction agent, time travel).
- `PLAN_v2_comprehensive_demo.md` — v2 command center design plan with [HELIX] design system spec.
- `databricks_showcase.html` — Original HTML prototype that inspired the showcase app.
