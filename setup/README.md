# Setup Notebooks

The setup workflow is split into two layers:

## Required (run via `./deploy.sh bootstrap`)

| File | What it does |
|---|---|
| `bootstrap_uc_objects.py` | Creates the catalog, schema, all Delta tables, demo data, UC functions, and Vector Search indexes — all under `{UC_CATALOG}.{UC_SCHEMA}`, matching what `agent.py` looks up at runtime. Run via `./deploy.sh bootstrap`. |

This single notebook replaces the old `00_create_catalog_schema.sql`,
`01_lakebase_schema.sql`, `02_vector_search_indexes.py`,
`03_uc_functions.sql`, `04_seed_demo_data.py`, `07_audit_tables.sql`, and
`07_audit_tables.py` files. Those scripts created objects across multiple
schemas (`gtm.crm`, `gtm.tools`, `gtm.vectors`, `gtm.audit`, etc.) that did
not match the agent's flat `{CATALOG}.{SCHEMA}.<name>` references — a hard
mismatch that broke every fresh deploy.

## Optional (run as standalone notebooks after bootstrap)

| File | What it does | When to run |
|---|---|---|
| `05_uc_governance.sql` | Row-level security + column masks on `gtm_accounts` / `gtm_contacts` | Optional: only if you want governance enforced |
| `06_lakewatch_rules.py` | 4 Lakewatch SQL alert rules (prompt injection, PII leakage, account scraping, outreach volume) | Optional: only if you want runtime alerts |
| `08_ai_gateway_config.py` | AI Gateway config on the LLM endpoint (rate limits, guardrails, inference tables) | Optional: requires CAN_MANAGE on the endpoint |

These are post-bootstrap, orthogonal concerns. They reference object names
that the bootstrap notebook creates, so always run `./deploy.sh bootstrap`
first.

## Lakebase memory tables

Lakebase Postgres memory (short-term `CheckpointSaver` + long-term
`DatabricksStore`) is set up separately via:

```
./deploy.sh lakebase
```

This runs `deployment/lakebase_memory_setup.py` which calls
`DatabricksStore.put()` to seed AE preferences, account context, and
deal decisions. The bootstrap above does not touch Lakebase.
