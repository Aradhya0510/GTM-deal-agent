# GTM Deal Intelligence Agent

**A multi-agent system for deal scoring, account research, and personalized outreach — powered by the full Databricks AI stack.**

This demo showcases how every layer of the Databricks platform comes together to build a production-grade AI agent for B2B sales teams. AEs interact with a Streamlit app that orchestrates a LangGraph multi-agent pipeline backed by Lakebase, Vector Search, UC Functions, Model Serving, and MLflow.

---

## What the Agent Does

| Capability | Description | Databricks Tech |
|---|---|---|
| **Account Research** | Pulls CRM data, call transcripts, engagement signals into a unified briefing | UC Functions + Vector Search |
| **Deal Scoring** | Scores deals 0-100 on health/velocity/engagement, surfaces risk flags | UC Functions + Model Serving |
| **Competitive Intel** | Retrieves battlecard snippets and win/loss stories for the deal context | Vector Search |
| **Personalized Outreach** | Generates emails grounded in specific account signals | LLM Gateway + Vector Search |
| **Memory** | Remembers AE preferences and account context across sessions | Lakebase + LangGraph Checkpointing |
| **Time Travel** | Branch from any conversation checkpoint to try a different angle | Lakebase CheckpointSaver |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Streamlit App (Databricks Apps)                                │
├─────────────────────────────────────────────────────────────────┤
│  LangGraph Multi-Agent Pipeline                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  load     │→│ research │→│ scoring  │→│ outreach │→ save   │
│  │  memory   │  │  agent   │  │  agent   │  │  agent   │  memory│
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│       ↕              ↕              ↕              ↕            │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Lakebase        Vector Search    UC Functions       │      │
│  │  (CRM + Memory)  (3 indexes)     (deal_health,      │      │
│  │                                    account_signals)  │      │
│  └──────────────────────────────────────────────────────┘      │
│       ↕                                                        │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Model Serving (Claude) │ MLflow 3.0 │ Unity Catalog │      │
│  │  LLM Gateway            │ Tracing    │ Governance    │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### Memory Architecture

- **Short-term** (session-scoped): LangGraph CheckpointSaver → Lakebase Postgres. Every node is checkpointed. Multi-turn, restart-safe, time-travel-capable.
- **Long-term** (cross-session): Memory extraction agent (Haiku) runs at session close. Writes AE preferences, account context, and deal decisions to Lakebase. Retrieved at next session start and injected into system prompts.

---

## Prerequisites

### Databricks Workspace

| Requirement | Details |
|---|---|
| **Unity Catalog** | Enabled, with permission to create catalogs and schemas |
| **Serverless SQL Warehouse** | For UC Function execution |
| **Lakebase Instance** | Provisioned, named `gtm-memory` (or configured in `configs/default.yaml`) |
| **Vector Search** | Endpoint enabled (`gtm_vs_endpoint`) |
| **Model Serving** | External model access configured (Claude via LLM Gateway) |
| **Databricks Apps** | Enabled for Streamlit deployment |
| **MLflow 3.x** | Included in DBR 17.3 LTS ML+ |

### Permissions

| Permission | Required For |
|---|---|
| `CREATE CATALOG` / `CREATE SCHEMA` | Infrastructure setup |
| `CREATE FUNCTION` on `gtm.tools` | UC Function registration |
| `CREATE TABLE` on `gtm.crm`, `gtm.enablement`, `gtm.eval` | Data seeding |
| `CAN_MANAGE` on Vector Search endpoint | Index creation |
| `CAN_QUERY` on Model Serving endpoints | Agent LLM calls |
| `CAN_USE` on Serverless SQL Warehouse | UC Function execution |
| `CAN_MANAGE` on Lakebase instance | Memory table creation |
| `CAN_CREATE` on Databricks Apps | App deployment |

### External Services (Optional)

| Service | Purpose | Setup |
|---|---|---|
| Salesforce MCP | Live CRM reads/writes | Configure in UC credential store |
| Gong MCP | Call transcript retrieval | Configure in UC credential store |

---

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url>
cd servicenow-gtm-agent
pip install -e ".[dev]"
```

### 2. Run infrastructure setup

Run the setup scripts in order as Databricks notebooks:

```
setup/00_create_catalog_schema.sql    # Create UC catalog + schemas
setup/01_lakebase_schema.sql          # Create Lakebase CRM + memory tables
setup/04_seed_demo_data.py            # Seed demo accounts, opps, transcripts
setup/02_vector_search_indexes.py     # Create Vector Search indexes (after seeding)
setup/03_uc_functions.sql             # Register UC Function tools
setup/05_uc_governance.sql            # Row-level security + column masking
setup/06_lakewatch_rules.py           # Security detection rules
```

### 3. Deploy the agent

```bash
python deployment/deploy_endpoint.py
```

This logs the agent to MLflow, registers in Unity Catalog, and deploys to Model Serving.

### 4. Deploy the app

```bash
python deployment/deploy_app.py
```

Deploys the Streamlit app to Databricks Apps. Share the URL with AEs.

### 5. Run evaluation

```bash
python evaluation/golden_dataset.py   # Generate eval scenarios
python evaluation/evaluate.py         # Run AI judge evaluation
```

---

## Project Structure

```
servicenow-gtm-agent/
├── app/                                # Streamlit app (primary demo interface)
│   ├── app.py                          #   Main app with Databricks tech callouts
│   ├── app.yaml                        #   Databricks App configuration
│   └── requirements.txt
├── setup/                              # Infrastructure scripts (run once)
│   ├── 00_create_catalog_schema.sql    #   Unity Catalog schemas
│   ├── 01_lakebase_schema.sql          #   Lakebase CRM + memory tables
│   ├── 02_vector_search_indexes.py     #   Vector Search indexes
│   ├── 03_uc_functions.sql             #   UC Function agent tools
│   ├── 04_seed_demo_data.py            #   Demo data (accounts, opps, transcripts)
│   ├── 05_uc_governance.sql            #   Row-level security + masking
│   └── 06_lakewatch_rules.py           #   Security detection rules
├── src/servicenow_gtm_agent/           # Agent Python package
│   ├── config.py                       #   Pydantic config from YAML
│   ├── state.py                        #   DealState TypedDict (shared graph state)
│   ├── prompts.py                      #   System prompts for each sub-agent
│   ├── graph.py                        #   LangGraph pipeline with memory nodes
│   ├── agents/                         #   Sub-agent definitions
│   │   ├── research.py                 #     Account context gathering
│   │   ├── scoring.py                  #     Deal health + risk scoring
│   │   ├── outreach.py                 #     Personalized email generation
│   │   └── memory_extractor.py         #     Session-close fact extraction
│   ├── tools/                          #   Databricks tool wrappers
│   │   ├── uc_functions.py             #     UC Function tools
│   │   ├── vector_search.py            #     Vector Search retrievers
│   │   └── mcp_connections.py          #     Salesforce + Gong MCP
│   ├── memory/                         #   Two-tier memory layer
│   │   ├── short_term.py               #     LangGraph CheckpointSaver
│   │   ├── long_term.py                #     Extraction + retrieval
│   │   └── prompt_builder.py           #     Memory → system prompt injection
│   └── serving/
│       └── agent_model.py              #   MLflow model wrapper for Model Serving
├── evaluation/
│   ├── golden_dataset.py               #   Eval scenario generation
│   └── evaluate.py                     #   MLflow eval with AI judges
├── deployment/
│   ├── deploy_endpoint.py              #   Model Serving deployment
│   └── deploy_app.py                   #   Databricks App deployment
├── monitoring/
│   └── dashboard_queries.sql           #   DBSQL dashboard queries
├── configs/
│   └── default.yaml                    #   Agent configuration
├── tests/
│   ├── test_config.py
│   └── test_state.py
└── gtm_implementation_guide.html       #   Design reference (7-phase plan)
└── gtm_memory_layer.html               #   Memory layer design reference
```

---

## Databricks Technology Showcase

This project demonstrates **13 Databricks capabilities** working together:

| # | Technology | Role in GTM Agent |
|---|---|---|
| 1 | **Databricks Apps** | AE-facing Streamlit interface |
| 2 | **LangGraph** | Multi-agent orchestration (Research → Scoring → Outreach) |
| 3 | **Lakebase** | CRM operational store + long-term memory + session checkpoints |
| 4 | **Vector Search** | Semantic retrieval (3 indexes: transcripts, battlecards, deal stories) |
| 5 | **UC Functions** | SQL agent tools (deal_health, account_signals) on serverless compute |
| 6 | **Model Serving** | LLM inference endpoints (Claude via external models) |
| 7 | **LLM Gateway** | Rate limits, PII filtering, token budgets per team |
| 8 | **MCP Connections** | Salesforce + Gong integration (no credentials in code) |
| 9 | **MLflow 3.0** | Full tracing per invocation + evaluation with AI judges |
| 10 | **Agent Evaluation** | Custom judges (personalization, groundedness, safety) |
| 11 | **Unity Catalog** | Row-level security by territory, column masking, lineage |
| 12 | **Lakewatch** | Prompt injection detection, PII exfiltration alerts, volume anomalies |
| 13 | **Databricks SDK** | Infrastructure setup, deployment, app management |

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
pytest tests/test_config.py -v

# Lint
ruff check src/ tests/
ruff format src/ tests/
```

---

## License

Internal demo — Databricks.
