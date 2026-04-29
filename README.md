# Databricks Agent Capabilities Demo

A production-grade stateful tool-calling agent that showcases **14+ Databricks platform capabilities** working together in a single end-to-end system. The core agent is general-purpose — it demonstrates how Lakebase Postgres memory, LangGraph orchestration, UC Functions, Vector Search, AI Gateway, Model Serving, and MLflow tracing combine into a real deployed agent. A GTM (Go-To-Market) deal intelligence scenario is layered on top as one concrete application of this agent architecture.

**Two interfaces, one agent:**

| Interface | Purpose |
|---|---|
| **Primary App** | Platform capability showcase — architecture diagrams, tool call visualization, memory inspection, security dashboard |
| **Showcase App** | The same agent applied to a GTM scenario — deal scoring, account research, competitive intel, outreach drafting across 6 industry verticals |
| **Agent Endpoint** | The underlying agent, callable by any client |

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
| 1 | **Lakebase Postgres** | Real Postgres instance backing both short-term checkpoints and long-term semantic memory store |
| 2 | **LangGraph** | Tool-calling loop: agent node routes to tool node on tool calls, loops until complete. Compiled with Lakebase checkpointer. |
| 3 | **ChatDatabricks** | LLM interface to Claude Sonnet 4.6 via Databricks Model Serving + AI Gateway |
| 4 | **UC TABLE Functions** | `calculate_deal_health` and `get_account_signals` — serverless SQL functions registered in Unity Catalog, called as LangGraph tools |
| 5 | **Vector Search** | 3 delta-sync indexes on a shared endpoint, queried via `VectorSearchRetrieverTool` for semantic retrieval |
| 6 | **Model Serving** | Agent deployed as `ResponsesAgent` endpoint with SSE streaming, auto-scaling, and MLflow tracing |
| 7 | **AI Gateway** | Rate limits, safety guardrails, PII blocking, payload logging to inference tables, usage tracking via system tables |
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
langgraph>=1.1.7
langgraph-checkpoint-postgres>=2.0.5
unitycatalog-langchain[databricks]>=0.3.0
databricks-agents
databricks-sdk>=0.65.0
pydantic
streamlit>=1.38
```

The deploy scripts pin these in the relevant places (job environments,
`pip_requirements` for the logged model). You don't need to install most of
them locally — only `databricks-sdk` and `streamlit` are needed for local dev.

---

## Setup and Deployment Guide

End-to-end deployment is driven by **one entry point**: `./deploy.sh`. It
reads `./.env` (gitignored, see `.env.example` for the template) and
dispatches to per-target scripts that render the right job spec or
`app.yaml` and submit it via the Databricks CLI. There is nothing to edit
in the Python sources — `agent.py`, the apps, and the notebooks all read
their config from environment variables or `dbutils.widgets`, populated at
deploy time.

### Step 1: Clone and Install

```bash
git clone <repo-url>
cd servicenow-gtm-agent
pip install -e ".[dev]"     # optional, only for local dev / tests
```

### Step 2: Configure Your Deployment

```bash
cp .env.example .env
# Edit .env with your workspace URL, catalog, schema, Lakebase instance,
# Vector Search endpoint, app names, etc.
```

`.env` is gitignored. `.env.example` documents every variable, grouped by
which deploy target consumes it. Required variables include
`DATABRICKS_PROFILE`, `UC_CATALOG`, `UC_SCHEMA`, `LAKEBASE_INSTANCE_NAME`,
`VS_ENDPOINT_NAME`, `SQL_WAREHOUSE_ID`, `MLFLOW_EXPERIMENT_NAME`, and
`AGENT_NOTEBOOK_WORKSPACE_PATH`. Optional but recommended:
`LAKEBASE_PAT_SECRET_SCOPE` / `LAKEBASE_PAT_SECRET_KEY` (for PAT-based
Lakebase auth — see Step 6).

### Step 3: Configure the Databricks CLI

```bash
databricks auth login --host https://<workspace>.cloud.databricks.com --profile <profile>
databricks auth profiles  # verify
```

The profile name must match `DATABRICKS_PROFILE` in `.env`.

### Step 4: Create the Lakebase Instance and PAT Secret

Provision a Lakebase Postgres instance (CU_1 is plenty for memory):

```bash
databricks --profile <profile> database create-database-instance <name> --capacity CU_1
```

Then store a Databricks PAT in a secret scope. The agent uses this PAT to
authenticate to Lakebase from Model Serving (where each `agents.deploy()`
creates a new ephemeral SP with no Postgres role — see CLAUDE.md learning
#18 for the full explanation):

```bash
databricks --profile <profile> secrets create-scope gtm-agent
databricks --profile <profile> secrets put-secret gtm-agent sql-write-token --string-value "<your-pat>"
```

Set `LAKEBASE_PAT_SECRET_SCOPE=gtm-agent` and
`LAKEBASE_PAT_SECRET_KEY=sql-write-token` in `.env` so the deploy scripts
reference this secret.

### Step 5: Bootstrap UC Objects

```bash
./deploy.sh bootstrap
```

Submits a serverless job that runs `setup/bootstrap_uc_objects.py`. That
notebook creates everything under `{UC_CATALOG}.{UC_SCHEMA}`:

- Catalog and schema (skip catalog creation by setting
  `BOOTSTRAP_CREATE_CATALOG=false` in `.env` if your catalog already exists
  with a managed location the metastore can't re-validate)
- Delta tables: `gtm_accounts`, `gtm_contacts`, `gtm_opportunities`,
  `gtm_outreach_log`, `gtm_call_transcripts`, `gtm_battlecards`,
  `gtm_deal_stories`, `audit_agent_access`
- Demo data seeded via SQL `INSERT` (idempotent — `TRUNCATE` first)
- UC functions: `calculate_deal_health`, `get_account_signals` (with
  `RETURNS TABLE(result STRING)` to avoid the correlated-subquery trap)
- Vector Search indexes: `gtm_transcripts_idx`, `gtm_battlecards_idx`,
  `gtm_stories_idx` (against your existing `VS_ENDPOINT_NAME`)

Index sync runs asynchronously after creation — check the Vector Search
UI for `Online` status before deploying the agent.

Note: the optional setup files (`05_uc_governance.sql`,
`06_lakewatch_rules.py`, `08_ai_gateway_config.py`) are orthogonal
post-bootstrap concerns. Run them as standalone notebooks if you want
governance, alerts, or AI Gateway config — they're not required for the
agent to work.

### Step 6: Seed Lakebase Memory and Grant Permissions

```bash
./deploy.sh lakebase
```

Seeds AE preferences, account context, and deal decisions into Lakebase via
`DatabricksStore.put()`.

> **Lakebase auth on Databricks Apps is workspace-dependent.** Some
> Lakebase instances auto-provision a `databricks_writer_<id>` Postgres role
> for every workspace user/SP, so the App SP authenticates natively via
> OAuth. Other instances do not — and on those, OAuth tokens minted for the
> App SP fail with `password authentication failed`. There is no
> documented way to mark a manually-created role as Lakebase-managed, so
> the universal workaround is to wire a PAT into the App the same way the
> agent does on Model Serving. The repo supports both paths: leave
> `LAKEBASE_PAT_SECRET_SCOPE` unset to use OAuth-only, or set it to wire
> a PAT secret resource into the App's `app.yaml`. **Recommendation:**
> always wire the PAT — it works in both cases.

You will also want per-SP Postgres role grants once the apps are deployed
(Step 9 below) — that's `./deploy.sh grants`, run after the app SPs exist.

### Step 7: Deploy the Agent to Model Serving

```bash
./deploy.sh agent
```

Uploads `deployment/agent.py` and `deployment/log_and_deploy_notebook.py`
to your workspace and submits a serverless job that calls
`mlflow.pyfunc.log_model()` and `agents.deploy()`. Takes 5-10 minutes for
the served entity to reach `DEPLOYMENT_READY`.

> **`GTM_ENDPOINT` reconciliation.** `agents.deploy()` derives the Model
> Serving endpoint name from the registered model name and **truncates** to
> the 63-char limit. The deployed name may not match what you put in
> `.env GTM_ENDPOINT`. The job log prints `Endpoint: <actual-name>` —
> reconcile `.env GTM_ENDPOINT` with that value before deploying the apps.

### Step 8: Deploy the Apps

```bash
./deploy.sh app          # main GTM v2 Command Center
./deploy.sh showcase     # Mission Control showcase
# or both at once:
./deploy.sh all-apps
```

Each script renders an `app.yaml` from `.env` (with real resource names + an
`env:` block populating `GTM_ENDPOINT`, `UC_CATALOG`, etc.), uploads the
sanitized Python sources, and calls `databricks apps deploy`. Errors out
with a helpful message if the target app doesn't exist
(`databricks apps create <name>` to create it first).

> **Databricks Apps quirk: `apps deploy` does not update the `resources:`
> array.** It uploads source files and the new `app.yaml` text but does
> NOT update the App's stored resource list. So a NEW resource (e.g.
> the `lakebase-pat` secret resource added when you set
> `LAKEBASE_PAT_SECRET_SCOPE` for the first time) won't actually attach
> until you run `apps update` once. The showcase deploy script prints the
> exact `apps update` and `secrets put-acl` commands at the end of its
> run when it adds a new secret resource — copy-paste them.

### Step 9: Apply Per-SP Postgres Grants

```bash
./deploy.sh grants
```

Auto-discovers the App service principal client IDs from
`databricks apps get` for both `APP_NAME` and `MAIN_APP_NAME`, then submits
`deployment/lakebase_grant_permissions.py` as a job that:

- Probes `pg_roles` for `databricks_users` (only chains `IN ROLE` if it
  exists)
- Creates a Postgres role per App SP UUID
- Grants `CONNECT` / `USAGE` / table privileges
- Falls back to `GRANT TO PUBLIC` for workspaces with auto-provisioned
  `databricks_writer_*` family roles

Each SQL statement runs in its own try/except and prints `[OK]` or
`[FAIL: <msg>]` — no DO-block error swallowing.

> If your apps still can't connect after this step, the manually-created
> roles may not validate OAuth tokens (CLAUDE.md learning #21). The PAT
> path from Step 6 is the universal fallback — it always works.

---

## Project Structure

```
servicenow-gtm-agent/
├── deploy.sh                           # Top-level dispatcher — bootstrap | lakebase | grants | agent | app | showcase
├── .env.example                        # Template for the local .env (gitignored)
├── deployment/                         # Core agent + deploy scripts
│   ├── agent.py                        #   LangGraph agent (7 tools, guardrails, ResponsesAgent)
│   ├── log_and_deploy_notebook.py      #   MLflow log_model() + agents.deploy() (widget-driven)
│   ├── lakebase_memory_setup.py        #   Seed data into Lakebase Postgres (widget-driven)
│   ├── lakebase_grant_permissions.py   #   Per-SP Postgres role creation (no DO blocks)
│   ├── deploy_agent.sh                 #   ./deploy.sh agent
│   ├── deploy_lakebase.sh              #   ./deploy.sh lakebase
│   ├── deploy_lakebase_grants.sh       #   ./deploy.sh grants (auto-discovers App SPs)
│   └── deploy_bootstrap.sh             #   ./deploy.sh bootstrap
├── app/                                # Primary app — platform capability showcase
│   ├── app.py                          #   5-tab Command Center ([HELIX] design)
│   ├── app.yaml                        #   Placeholder; deploy.sh renders the real one from .env
│   ├── deploy.sh                       #   ./deploy.sh app
│   └── requirements.txt
├── showcase/                           # Showcase app — GTM scenario demo
│   ├── app.py                          #   6-page app (Briefing, Deal Room, Architecture, etc.)
│   ├── backend.py                      #   DatabricksStore + agent calls (PAT path with auth_type=pat)
│   ├── data.py                         #   6 industry vertical demo data
│   ├── styles.py                       #   ServiceNow branding CSS
│   ├── components.py                   #   X-Ray, DAG, tool card renderers
│   ├── app.yaml                        #   Placeholder; deploy.sh renders the real one from .env
│   ├── deploy.sh                       #   ./deploy.sh showcase
│   └── requirements.txt
├── setup/                              # Bootstrap notebook + optional post-bootstrap layers
│   ├── README.md                       #   What's required vs optional
│   ├── bootstrap_uc_objects.py         #   Required: catalog + schema + tables + funcs + VS indexes
│   ├── 05_uc_governance.sql            #   Optional: RLS + column masking
│   ├── 06_lakewatch_rules.py           #   Optional: security alert rules
│   └── 08_ai_gateway_config.py         #   Optional: AI Gateway config
├── src/servicenow_gtm_agent/           # Reference implementation for local dev
├── configs/                            # Workspace-specific YAML configs
├── tests/
├── .cursor/skills/
│   └── databricks-agent-guide/SKILL.md #   Cursor skill for Databricks agent development
├── CLAUDE.md                           #   Claude Code guidance + deployment learnings (local only)
├── DEPLOYMENT_NOTES.md                 #   Field-deploy log from a customer workspace
└── README.md
```

---

## Key Design Decisions

**Agent code is separate from deployment code.** `agent.py` contains only the agent definition + `set_model()`. The `log_and_deploy_notebook.py` calls `log_model()` and `deploy()` separately. Mixing them causes infinite recursion because `log_model()` re-executes the target file.

**Memory is a visible tool, not hidden pre-processing.** `recall_lakebase_memory` and `store_lakebase_memory` are `@tool` functions that appear in tool call X-Ray cards. This makes memory operations visible in the demo UI alongside UC Functions and Vector Search, which is critical for demonstrating the Lakebase capability.

**PAT auth for Lakebase, in two contexts.** `agents.deploy()` creates a new
invisible SP per model version with no Postgres role, so the agent on Model
Serving must use a stable PAT (from Databricks Secrets) that authenticates
as a user with a Lakebase-managed role. **On Databricks Apps the same PAT
path is recommended** — some Lakebase instances do not auto-provision a
`databricks_writer_<id>` role for the App SP, and a hand-created role can't
validate OAuth tokens (CLAUDE.md learning #21). The repo supports both
modes: leave `LAKEBASE_PAT_SECRET_SCOPE` unset to fall back to OAuth
(works on workspaces with auto-provisioned roles), or set it to wire a
`secret` resource into `app.yaml` and bind `LAKEBASE_PAT` at runtime. The
PAT path is the universal fallback that works in either case.

**UC Functions use RETURNS TABLE, not scalar RETURNS STRING.** Scalar UC SQL functions treat the body as a correlated subquery when referencing parameters. `RETURNS TABLE(result STRING)` avoids this.

**Reuse warmed VS endpoints.** Creating a new VS endpoint takes 20-30 minutes. Using an existing active endpoint creates indexes in under 1 minute.

---

## Workspace Assets

After deployment, your workspace will contain these assets (names depend on your catalog/schema config):

| Asset Type | Description |
|---|---|
| **Lakebase Instance** | Postgres instance for memory (short-term checkpoints + long-term DatabricksStore) |
| **CRM Tables** | `gtm_accounts`, `gtm_contacts`, `gtm_opportunities`, `gtm_outreach_log`, `gtm_call_transcripts`, `gtm_battlecards`, `gtm_deal_stories` |
| **Audit Table** | `audit_agent_access` — security event logging |
| **VS Endpoint** | Shared Vector Search endpoint |
| **VS Indexes** | `gtm_transcripts_idx`, `gtm_battlecards_idx`, `gtm_stories_idx` |
| **UC Functions** | `calculate_deal_health`, `get_account_signals` |
| **Model** | Registered MLflow model in Unity Catalog |
| **Serving Endpoint** | Auto-created by `agents.deploy()` |
| **AI Gateway** | Configured on LLM endpoint (rate limits, guardrails, inference tables) |
| **Embedding Model** | `databricks-gte-large-en` (1024 dim) for memory semantic search |
| **SQL Warehouse** | Serverless warehouse for UC Function execution and audit writes |
| **MLflow Experiment** | Traces for every agent invocation |
| **Secrets** | PAT for Lakebase auth from Model Serving |

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
