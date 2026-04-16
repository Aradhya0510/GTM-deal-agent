# Databricks Agent Capabilities Demo

A production-grade stateful tool-calling agent that showcases **14+ Databricks platform capabilities** working together in a single end-to-end system. The core agent is general-purpose — it demonstrates how Lakebase Postgres memory, LangGraph orchestration, UC Functions, Vector Search, AI Gateway, Model Serving, and MLflow tracing combine into a real deployed agent. A GTM (Go-To-Market) deal intelligence scenario is layered on top as one concrete application of this agent architecture.

**Two interfaces, one agent:**

| Interface | Purpose | URL |
|---|---|---|
| **Primary App** | Platform capability showcase — architecture diagrams, tool call visualization, memory inspection, security dashboard | `https://gtm-deal-intelligence-2556758628403379.aws.databricksapps.com` |
| **Showcase App** | The same agent applied to a GTM scenario — deal scoring, account research, competitive intel, outreach drafting across 6 industry verticals | `https://mission-control-2556758628403379.aws.databricksapps.com` |
| **Agent Endpoint** | The underlying agent, callable by any client | `agents_users-aradhya_chouhan-gtm_deal_intelligence_agent` |

**Workspace:** `e2-demo-west.cloud.databricks.com`

---

## What This Project Demonstrates

The core contribution is showing how every layer of the Databricks AI platform connects into a single working agent. The GTM data and scenario are demo content — the architecture, patterns, and deployment learnings are the real value.

### Agent Capabilities (General)

| Capability | How It Works | Databricks Features |
|---|---|---|
| **Stateful Memory (Short-term)** | LangGraph state persisted to Postgres after every turn; survives replicas and restarts | Lakebase Postgres + `CheckpointSaver` |
| **Stateful Memory (Long-term)** | Key-value store with embedding-based semantic search; preferences and context persist across sessions | Lakebase Postgres + `DatabricksStore` + `databricks-gte-large-en` |
| **Tool Calling** | Agent autonomously selects and calls tools in a loop until the task is complete | LangGraph + `ToolNode` |
| **Serverless SQL Tools** | SQL functions registered in Unity Catalog, callable as LangGraph tools without managing compute | UC TABLE Functions + `UCFunctionToolkit` |
| **Semantic Retrieval** | Delta-sync vector indexes queried via natural language for grounded responses | Vector Search + `VectorSearchRetrieverTool` |
| **LLM with Guardrails** | All LLM traffic routed through AI Gateway with rate limits, safety filters, PII blocking, and payload logging | AI Gateway + `ChatDatabricks` |
| **Inline Security** | Pre-request injection detection (12 regex patterns) + post-response PII scan, logged to audit table | Custom guardrails in agent code |
| **Streaming Responses** | SSE streaming from Model Serving to Streamlit with per-tool-call progress cards | `ResponsesAgent` + `output_to_responses_items_stream` |
| **Full Observability** | Every invocation traced: tool calls, LLM I/O, latency, token counts | MLflow Tracing + AI Gateway inference tables |
| **Declarative Deployment** | Agent logged to MLflow, registered in UC, deployed to Model Serving with resource declarations | `mlflow.pyfunc.log_model()` + `agents.deploy()` |

### GTM Scenario (Showcase Application)

The showcase app applies this agent to a B2B sales use case with demo data across 6 industry verticals (Financial Services, Healthcare, Retail, Manufacturing, Technology, Energy):

- **Deal health scoring** — UC Function scores opportunities 0-100 with risk flags
- **Account 360** — UC Function pulls contacts, opportunities, ARR signals
- **Transcript search** — Vector Search over Gong call transcripts for recent context
- **Competitive intel** — Vector Search over battlecards and won/lost deal stories
- **Personalized outreach** — Emails, LinkedIn messages, call talk tracks grounded in real signals and shaped by AE preferences from memory
- **Memory-informed behavior** — Agent recalls each AE's email style, word limits, CTA preferences, competitors to avoid

---

## Databricks Features Showcase

| # | Feature | Role in This Agent |
|---|---|---|
| 1 | **Lakebase Postgres** | Real Postgres instance (`gtm-agent-memory`) backing both short-term checkpoints and long-term semantic memory store |
| 2 | **LangGraph** | Tool-calling loop: agent node routes to tool node on tool calls, loops until complete. Compiled with Lakebase checkpointer. |
| 3 | **ChatDatabricks** | LLM interface to Claude Sonnet 4.6 via Databricks Model Serving + AI Gateway |
| 4 | **UC TABLE Functions** | `calculate_deal_health` and `get_account_signals` — serverless SQL functions registered in Unity Catalog, called as LangGraph tools |
| 5 | **Vector Search** | 3 delta-sync indexes on a shared endpoint, queried via `VectorSearchRetrieverTool` for semantic retrieval |
| 6 | **Model Serving** | Agent deployed as `ResponsesAgent` endpoint with SSE streaming, auto-scaling, and MLflow tracing |
| 7 | **AI Gateway** | Rate limits (60 QPM), safety guardrails, PII blocking, payload logging to inference tables, usage tracking via system tables |
| 8 | **MLflow Tracing** | `mlflow.langchain.autolog()` traces every invocation — tool calls, LLM inputs/outputs, latency |
| 9 | **Unity Catalog Governance** | Row-level security by territory, column masking on sensitive fields, function-level access control |
| 10 | **Lakewatch** | 4 SQL alert rules: prompt injection detection, PII in output, broad account scraping, outreach volume spikes |
| 11 | **Databricks Apps** | Two Streamlit apps with auto-injected auth, resource declarations, and service principal permissions |
| 12 | **Databricks Secrets** | `LAKEBASE_PAT` for agent-to-Lakebase auth on Model Serving, injected via `environment_vars` |
| 13 | **Databricks SDK** | WorkspaceClient for SQL Statement Execution API (audit logging), job submission, app deployment |
| 14 | **Embedding Models** | `databricks-gte-large-en` (1024-dim) powers semantic search in DatabricksStore for memory recall |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Streamlit App (Databricks Apps)                                        │
│  ├── Primary: capability showcase (architecture, memory, security)       │
│  └── Showcase: GTM scenario (deal room, pipeline, outreach studio)       │
├─────────────────────────────────────────────────────────────────────────┤
│  Model Serving Endpoint (ResponsesAgent)                                │
│  ┌──────────────┐                                                       │
│  │ Pre-Guardrail│ → Regex injection scan (12 patterns)                  │
│  └──────┬───────┘                                                       │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │  LangGraph Tool-Calling Loop                                 │       │
│  │                                                              │       │
│  │  Agent Node (ChatDatabricks → AI Gateway → Claude Sonnet)    │       │
│  │       ↕ tool calls                                           │       │
│  │  Tools Node:                                                 │       │
│  │    ├─ recall_lakebase_memory  (Lakebase Postgres)            │       │
│  │    ├─ store_lakebase_memory   (Lakebase Postgres)            │       │
│  │    ├─ calculate_deal_health   (UC Function)                  │       │
│  │    ├─ get_account_signals     (UC Function)                  │       │
│  │    ├─ gtm_transcripts_idx     (Vector Search)                │       │
│  │    ├─ gtm_battlecards_idx     (Vector Search)                │       │
│  │    └─ gtm_stories_idx         (Vector Search)                │       │
│  │                                                              │       │
│  │  CheckpointSaver → Lakebase Postgres (state per turn)        │       │
│  └──────────────────────────────────────────────────────────────┘       │
│         ▼                                                               │
│  ┌───────────────┐                                                      │
│  │ Post-Guardrail│ → PII scan (email, phone, SSN) → audit log           │
│  └───────────────┘                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Memory Architecture

**Short-term** (within a session): `CheckpointSaver` from `databricks_langchain` writes LangGraph state to Lakebase Postgres after every agent turn. Enables multi-turn follow-ups and cross-replica session persistence via `thread_id`.

**Long-term** (across sessions): `DatabricksStore` from `databricks_langchain[memory]` provides a namespaced key-value store in Lakebase Postgres with **semantic search** via `databricks-gte-large-en` embeddings. The agent calls `recall_lakebase_memory` as a visible tool on every query — it searches using embedding similarity, not rigid SQL WHERE clauses. The agent calls `store_lakebase_memory` to persist new facts in real-time. At session end, a haiku-powered extraction agent batch-writes discovered facts.

Memory is implemented as visible `@tool` functions (not hidden pre-processing) so recall and store operations appear in the tool call X-Ray cards alongside UC Functions and Vector Search.

---

## Prerequisites

### Databricks Workspace

| Requirement | Details |
|---|---|
| **Unity Catalog** | Enabled, with permission to create catalogs, schemas, functions, and tables |
| **Serverless SQL Warehouse** | For UC Function execution and audit table writes |
| **Lakebase Postgres** | A provisioned instance (CU_1 minimum) |
| **Vector Search** | An active VS endpoint (reuse an existing warmed endpoint to avoid 20-30 min provisioning) |
| **Model Serving** | External model access for Claude (via `databricks-claude-sonnet-4-6` endpoint) |
| **AI Gateway** | Configured on the LLM endpoint with usage tracking, rate limits, and guardrails |
| **Embedding Model** | `databricks-gte-large-en` endpoint active (for DatabricksStore semantic search) |
| **Databricks Apps** | Enabled in the workspace |
| **Databricks Secrets** | A secret scope with a PAT key for Lakebase auth from Model Serving |
| **Databricks CLI** | v0.250+ with a workspace profile configured |

### Permissions

| Permission | Resource | Required For |
|---|---|---|
| `CREATE CATALOG` / `CREATE SCHEMA` | Unity Catalog | Infrastructure setup |
| `CREATE FUNCTION` | Target schema | Registering UC Function tools |
| `CREATE TABLE` | Target schema | Seeding demo data |
| `CAN_MANAGE` | Vector Search endpoint | Creating delta-sync indexes |
| `CAN_QUERY` | Model Serving endpoints | Agent LLM + embedding calls |
| `CAN_USE` | Serverless SQL Warehouse | UC Function execution |
| `CAN_MANAGE` | Lakebase instance | Instance creation, granting Postgres roles |
| `CAN_USE` | Lakebase instance | App and agent read/write access |
| `CAN_CREATE` | Databricks Apps | Deploying Streamlit apps |
| `CAN_MANAGE` | LLM Serving Endpoint | Configuring AI Gateway |

### Python Dependencies

```
mlflow>=3.6.0
databricks-langchain[memory]>=0.17.0
langgraph>=0.3
langgraph-checkpoint-postgres>=2.0.5
databricks-agents
databricks-sdk>=0.65.0
pydantic
streamlit>=1.38
```

---

## Setup and Deployment Guide

All commands use `databricks --profile <your-profile>`. Replace `<you>` with your workspace username.

### Step 1: Clone and Install

```bash
git clone <repo-url>
cd servicenow-gtm-agent
pip install -e ".[dev]"
```

### Step 2: Configure CLI

```bash
databricks auth login --host https://<workspace>.cloud.databricks.com
databricks auth profiles  # verify
```

### Step 3: Create Lakebase Postgres Instance

```bash
databricks --profile <profile> database create-database-instance gtm-agent-memory --capacity CU_1
```

### Step 4: Run Infrastructure Setup

Run as Databricks notebooks in this order:

| Order | Script | Purpose |
|---|---|---|
| 1 | `setup/00_create_catalog_schema.sql` | Unity Catalog catalog + schemas |
| 2 | `setup/01_lakebase_schema.sql` | Lakebase CRM tables (if applicable) |
| 3 | `setup/04_seed_demo_data.py` | Demo CRM data (accounts, contacts, opportunities, transcripts, battlecards, stories) |
| 4 | `setup/02_vector_search_indexes.py` | 3 delta-sync VS indexes (use existing warmed endpoint) |
| 5 | `setup/03_uc_functions.sql` | UC TABLE Functions (`calculate_deal_health`, `get_account_signals`) |
| 6 | `setup/05_uc_governance.sql` | Row-level security + column masking |
| 7 | `setup/06_lakewatch_rules.py` | Security alert rules |
| 8 | `setup/07_audit_tables.py` | `audit_agent_access` Delta table |
| 9 | `setup/08_ai_gateway_config.py` | AI Gateway on LLM endpoint |

Source tables need `delta.enableChangeDataFeed = true` BEFORE creating VS indexes.

### Step 5: Seed Lakebase Memory

```bash
databricks --profile <profile> workspace import \
  /Workspace/Users/<you>/servicenow-gtm-agent/lakebase_memory_setup \
  --file deployment/lakebase_memory_setup.py --format SOURCE --language PYTHON --overwrite

databricks --profile <profile> jobs submit --json '{
  "run_name": "memory-seed",
  "tasks": [{"task_key": "setup", "notebook_task": {
    "notebook_path": "/Workspace/Users/<you>/servicenow-gtm-agent/lakebase_memory_setup",
    "source": "WORKSPACE"}, "environment_key": "default"}],
  "environments": [{"environment_key": "default", "spec": {"client": "2",
    "dependencies": ["databricks-langchain[memory]>=0.17.0","langgraph-checkpoint-postgres>=2.0.5"]}}]
}'
```

### Step 6: Grant Lakebase Permissions

Workspace-level:

```bash
databricks --profile <profile> api patch \
  /api/2.0/permissions/database-instances/gtm-agent-memory --json '{
  "access_control_list": [{"group_name": "users", "permission_level": "CAN_USE"}]
}'
```

Postgres-level (run `deployment/lakebase_grant_permissions.py` as a notebook — this grants `PUBLIC` access so any authenticated identity can connect):

```bash
databricks --profile <profile> workspace import \
  /Workspace/Users/<you>/servicenow-gtm-agent/lakebase_grant_permissions \
  --file deployment/lakebase_grant_permissions.py --format SOURCE --language PYTHON --overwrite

databricks --profile <profile> jobs submit --json '{
  "run_name": "lakebase-grants",
  "tasks": [{"task_key": "grant", "notebook_task": {
    "notebook_path": "/Workspace/Users/<you>/servicenow-gtm-agent/lakebase_grant_permissions",
    "source": "WORKSPACE"}, "environment_key": "default"}],
  "environments": [{"environment_key": "default", "spec": {"client": "2",
    "dependencies": ["databricks-langchain[memory]>=0.17.0","langgraph-checkpoint-postgres>=2.0.5","databricks-ai-bridge[memory]>=0.17.0"]}}]
}'
```

### Step 7: Create Lakebase PAT Secret

Model Serving's auto-generated SP cannot authenticate to Lakebase Postgres natively (it creates a new invisible SP per model version with no Postgres role). Store a stable PAT:

```bash
databricks --profile <profile> secrets create-scope gtm-agent  # if scope doesn't exist
databricks --profile <profile> secrets put-secret gtm-agent sql-write-token --string-value "<your-pat>"
```

### Step 8: Deploy the Agent

```bash
databricks --profile <profile> workspace import \
  /Workspace/Users/<you>/servicenow-gtm-agent/agent.py \
  --file deployment/agent.py --format AUTO --overwrite

databricks --profile <profile> workspace import \
  /Workspace/Users/<you>/servicenow-gtm-agent/log_and_deploy \
  --file deployment/log_and_deploy_notebook.py --format SOURCE --language PYTHON --overwrite

databricks --profile <profile> jobs submit --json '{
  "run_name": "agent-deploy",
  "tasks": [{"task_key": "log_and_deploy", "notebook_task": {
    "notebook_path": "/Workspace/Users/<you>/servicenow-gtm-agent/log_and_deploy",
    "source": "WORKSPACE"}, "environment_key": "default"}],
  "environments": [{"environment_key": "default", "spec": {"client": "2",
    "dependencies": ["mlflow>=3.6.0","databricks-langchain[memory]>=0.17.0","langgraph>=0.3",
    "langgraph-checkpoint-postgres>=2.0.5","databricks-agents","pydantic",
    "unitycatalog-langchain[databricks]>=0.3.0"]}}]
}'
```

Wait 5-10 minutes for containers to reach `DEPLOYMENT_READY`.

### Step 9: Deploy the Primary App (Platform Showcase)

```bash
databricks --profile <profile> workspace import \
  /Workspace/Users/<you>/servicenow-gtm-agent/app/app.py \
  --file app/app.py --format AUTO --overwrite

databricks --profile <profile> apps deploy gtm-deal-intelligence \
  --source-code-path /Workspace/Users/<you>/servicenow-gtm-agent/app
```

### Step 10: Deploy the Showcase App (GTM Scenario)

```bash
for f in app.py backend.py data.py styles.py components.py app.yaml requirements.txt; do
  databricks --profile <profile> workspace import \
    /Workspace/Users/<you>/mission-control/$f \
    --file showcase/$f --format AUTO --overwrite
done

databricks --profile <profile> apps deploy mission-control \
  --source-code-path /Workspace/Users/<you>/mission-control
```

---

## Project Structure

```
servicenow-gtm-agent/
├── deployment/                         # Core agent + deployment
│   ├── agent.py                        #   LangGraph agent (7 tools, guardrails, ResponsesAgent)
│   ├── log_and_deploy_notebook.py      #   MLflow log_model() + agents.deploy()
│   ├── lakebase_memory_setup.py        #   Seed data into Lakebase Postgres
│   └── lakebase_grant_permissions.py   #   Grant Postgres roles for SPs
├── app/                                # Primary app — platform capability showcase
│   ├── app.py                          #   5-tab Command Center ([HELIX] design)
│   ├── app.yaml
│   └── requirements.txt
├── showcase/                           # Showcase app — GTM scenario demo
│   ├── app.py                          #   6-page app (Briefing, Deal Room, Architecture, etc.)
│   ├── backend.py                      #   Lakebase DatabricksStore + agent calls
│   ├── data.py                         #   6 industry vertical demo data
│   ├── styles.py                       #   ServiceNow branding CSS
│   ├── components.py                   #   X-Ray, DAG, tool card renderers
│   ├── app.yaml                        #   Endpoint + Lakebase resource declarations
│   └── requirements.txt
├── setup/                              # Infrastructure scripts (run once)
│   ├── 00_create_catalog_schema.sql    #   UC catalog + schemas
│   ├── 01_lakebase_schema.sql          #   Lakebase CRM tables
│   ├── 02_vector_search_indexes.py     #   3 delta-sync VS indexes
│   ├── 03_uc_functions.sql             #   UC TABLE Function tools
│   ├── 04_seed_demo_data.py            #   Demo CRM data
│   ├── 05_uc_governance.sql            #   RLS + column masking
│   ├── 06_lakewatch_rules.py           #   Security alert rules
│   ├── 07_audit_tables.py              #   Audit Delta table
│   └── 08_ai_gateway_config.py         #   AI Gateway config
├── src/servicenow_gtm_agent/           # Reference implementation for local dev
├── configs/                            # Workspace-specific YAML configs
├── tests/
├── .cursor/skills/
│   └── databricks-agent-guide/SKILL.md #   Cursor skill for Databricks agent development
├── CLAUDE.md                           #   Claude Code guidance + 23 deployment learnings
└── README.md
```

---

## Key Design Decisions

**Agent code is separate from deployment code.** `agent.py` contains only the agent definition + `set_model()`. The `log_and_deploy_notebook.py` calls `log_model()` and `deploy()` separately. Mixing them causes infinite recursion because `log_model()` re-executes the target file.

**Memory is a visible tool, not hidden pre-processing.** `recall_lakebase_memory` and `store_lakebase_memory` are `@tool` functions that appear in tool call X-Ray cards. This makes memory operations visible in the demo UI alongside UC Functions and Vector Search, which is critical for demonstrating the Lakebase capability.

**PAT auth for Lakebase on Model Serving.** `agents.deploy()` creates a new invisible SP per model version with no Postgres role. A stable PAT (from Databricks Secrets) authenticates as the instance owner. On Databricks Apps, the SP is stable and authenticates natively — no PAT needed.

**UC Functions use RETURNS TABLE, not scalar RETURNS STRING.** Scalar UC SQL functions treat the body as a correlated subquery when referencing parameters. `RETURNS TABLE(result STRING)` avoids this.

**Reuse warmed VS endpoints.** Creating a new VS endpoint takes 20-30 minutes. Using an existing active endpoint (like `dbdemos_vs_endpoint`) creates indexes in under 1 minute.

---

## Workspace Assets

| Asset | Name |
|---|---|
| **Lakebase Instance** | `gtm-agent-memory` (uid: `ce28def2-7d60-4a3d-83de-a150662e70be`) |
| **CRM Tables** | `users.aradhya_chouhan.gtm_accounts`, `gtm_contacts`, `gtm_opportunities`, `gtm_outreach_log`, `gtm_call_transcripts`, `gtm_battlecards`, `gtm_deal_stories` |
| **Audit Table** | `users.aradhya_chouhan.audit_agent_access` |
| **VS Endpoint** | `dbdemos_vs_endpoint` |
| **VS Indexes** | `users.aradhya_chouhan.gtm_transcripts_idx`, `gtm_battlecards_idx`, `gtm_stories_idx` |
| **UC Functions** | `users.aradhya_chouhan.calculate_deal_health`, `get_account_signals` |
| **Model** | `users.aradhya_chouhan.gtm_deal_intelligence_agent` |
| **Serving Endpoint** | `agents_users-aradhya_chouhan-gtm_deal_intelligence_agent` |
| **AI Gateway** | `databricks-claude-sonnet-4-6` (60 QPM, safety + PII guardrails) |
| **Embedding Model** | `databricks-gte-large-en` (1024 dim) |
| **SQL Warehouse** | `75fd8278393d07eb` (audit writes only) |
| **MLflow Experiment** | `/Users/aradhya.chouhan@databricks.com/gtm-deal-intelligence` |
| **Secrets** | Scope `gtm-agent`, key `sql-write-token` |

---

## Development

```bash
pip install -e ".[dev]"               # Install with dev dependencies
pytest                                # Run all tests
pytest tests/test_config.py -v        # Single test
ruff check src/ tests/                # Lint
ruff format src/ tests/               # Format
```

---

## License

Internal demo — Databricks.
