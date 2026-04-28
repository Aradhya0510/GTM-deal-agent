# Deployment Walkthrough: fevm-dolby-soundsight

A first-hand log of deploying this repo end-to-end into the
`fevm-dolby-soundsight` workspace, the issues encountered, and the fixes
applied. Separated into:

- **Repo-level fixes** — bugs / gaps in the repo itself; should be PR'd back upstream so the next person doesn't hit them.
- **Workspace-specific decisions** — choices made to fit this particular
  workspace; document for the customer / your future self, but don't change the repo.

---

## 1. Target State

| Component | Value |
|---|---|
| Workspace | `fevm-dolby-soundsight.cloud.databricks.com` (id `7474651104624510`) |
| CLI profile | `fe-vm-dolby-soundsight` |
| UC catalog / schema | `dolby_soundsight_catalog.gtm_agent` |
| Lakebase instance | `dolby-portal-db` (existing) |
| Vector Search endpoint | `soundsight-vs-endpoint` (existing) |
| SQL warehouse | `3f0ba1cfb2f640e6` (existing serverless) |
| Agent LLM | `databricks-claude-sonnet-4-6` |
| Memory LLM | `databricks-claude-haiku-4-5` |
| Embeddings | `databricks-gte-large-en` |
| Model Serving endpoint | `agents_dolby_soundsight_catalog-gtm_agent-gtm_deal_intelligence` |
| Apps | `mission-control` (showcase) + `gtm-deal-intelligence` (main) |

---

## 2. Deploy Order (what actually worked)

1. `databricks auth login --profile fe-vm-dolby-soundsight ...` — authenticate CLI
2. `databricks workspace mkdirs ...` — create workspace folders for notebooks + apps
3. `./deploy.sh bootstrap` — provision UC tables, functions, VS indexes
4. `./deploy.sh lakebase` — seed Lakebase memory tables
5. `./deploy.sh grants` — grant Lakebase Postgres permissions (workspace + Postgres + per-SP roles)
6. `databricks api patch /api/2.0/permissions/database-instances/<inst>` — workspace-level CAN_USE for `users`
7. `databricks secrets create-scope gtm-agent` + `put-secret` — store Lakebase PAT
8. `./deploy.sh agent` — log + register + deploy the agent
9. `./deploy.sh app` and `./deploy.sh showcase` — deploy both Streamlit apps

---

## 3. Repo-level Fixes (PR these back)

These are real bugs / gaps in the repo. They tripped up a first-time deploy and
will trip up the next person.

### 3.1 `agent.py` env vars not present at MLflow `log_model` time

**Symptom:** Agent deploy job failed with
`MlflowException: Failed to run user code ... Error: GetFunction invalid full_name_arg.`

**Root cause:** `mlflow.pyfunc.log_model(python_model="agent.py", ...)`
introspects `agent.py` by importing it. The agent reads `os.environ["UC_CATALOG"]`
etc. at module scope to construct fully-qualified names like
`{CATALOG}.{SCHEMA}.calculate_deal_health`. In the deploy notebook those values
were only set as MLflow `model_config` / `code_paths` parameters — they were
never exported into `os.environ` before the import.

**Fix:** In `deployment/log_and_deploy_notebook.py`, explicitly export the
notebook widgets to `os.environ` before calling `log_model`:

```python
import os
os.environ["UC_CATALOG"] = UC_CATALOG
os.environ["UC_SCHEMA"] = UC_SCHEMA
os.environ["LLM_ENDPOINT"] = LLM_ENDPOINT
os.environ["MEMORY_LLM_ENDPOINT"] = MEMORY_LLM_ENDPOINT
os.environ["DATABRICKS_EMBEDDING_ENDPOINT"] = DATABRICKS_EMBEDDING_ENDPOINT
os.environ["LAKEBASE_INSTANCE_NAME"] = LAKEBASE_INSTANCE_NAME
# ... etc
```

This is a strict bug — without it, `log_model` cannot succeed in any workspace.

### 3.2 `langgraph` pin too loose (>=0.3) breaks `databricks-langchain` 0.19+

**Symptom:** Agent deploy failed with
`cannot import name 'ExecutionInfo' from 'langgraph.runtime'`.

**Root cause:** `databricks-langchain >= 0.19.0` requires `langchain >= 1.0`
and uses `ExecutionInfo` from `langgraph.runtime`, which was only added in
`langgraph >= 1.x`. The repo pinned `langgraph >= 0.3`, which resolved to a
0.5.x build that does not have `ExecutionInfo`.

**Fix:** Bump the floor to `langgraph >= 1.1.7` in:

- `deployment/deploy_agent.sh` (job environment dependencies)
- `deployment/log_and_deploy_notebook.py` (`pip_requirements` for the logged model)
- `README.md` (Step 8 dependency list)

Also add `unitycatalog-langchain[databricks] >= 0.3.0` — the agent imports
`UCFunctionToolkit` from this package and it isn't pulled in transitively in
all environments.

### 3.3 `audit_agent_access` table uses `DEFAULT current_timestamp()` without enabling the Delta feature

**Symptom:** Bootstrap job failed with
`[WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED] Failed to execute CREATE TABLE command because it assigned a column DEFAULT value...`

**Root cause:** The bootstrap notebook created `audit_agent_access` with
`created_at TIMESTAMP DEFAULT current_timestamp()`. Delta column defaults
require `delta.feature.allowColumnDefaults` in `TBLPROPERTIES`, which the
bootstrap didn't enable.

**Fix (chosen):** Drop `DEFAULT current_timestamp()` from the column
definition. The agent's audit-write path explicitly passes
`current_timestamp()` in every INSERT, so the DEFAULT is unused anyway.

**Alternative fix:** Add `TBLPROPERTIES('delta.feature.allowColumnDefaults' = 'supported')`. Pick one; my repo PR uses the simpler "drop the unused default" approach.

### 3.4 Setup scripts and `agent.py` disagreed on UC layout

**Symptom:** Agent deploy failed with
`ResourceDoesNotExist: Routine or Model 'dolby_soundsight_catalog.gtm_agent.calculate_deal_health' does not exist.`

**Root cause:** The original `setup/` SQL scripts created tables / functions
in a multi-schema layout (`crm`, `gtm`, `vector_sources`, etc.), but
`agent.py` reads `UC_CATALOG` and `UC_SCHEMA` from `os.environ` and
constructs **flat** `{CATALOG}.{SCHEMA}.<name>` references for tools, indexes,
and tables. The two never agreed.

**Fix:** Replaced the multi-file SQL bootstrap with a single Python notebook
`setup/bootstrap_uc_objects.py` that creates everything (tables, functions,
VS indexes) under `{CATALOG}.{SCHEMA}` to match what the agent actually
references. Wired it into `deploy.sh bootstrap` via
`deployment/deploy_bootstrap.sh`.

### 3.5 `accounts_schema` had `employee_count` typed as `StringType()`

**Symptom:** Caught during code review — would have produced a runtime cast
error against the seed CSV / agent SQL.

**Fix:** Changed to `LongType()` in `setup/bootstrap_uc_objects.py` to match
the `01_lakebase_schema.sql` `INTEGER` column and the demo seed.

### 3.6 Lakebase auth from Databricks Apps — the full story

This was the single longest deploy issue. The README's claim
*"On Databricks Apps, the SP is stable and authenticates natively — no PAT
needed"* did not hold in this workspace, and getting it working required four
layered fixes. Documenting all of them because each was real:

**Symptom (recurring):**
```
error connecting in 'pool-1': connection failed: ... port 5432 failed:
ERROR: password authentication failed for user '<app-sp-uuid>'
```

**Layer 1 — Workspace permission:** the `users` group did not have `CAN_USE`
on the Lakebase instance, and neither did the App SPs. App SPs are also not
members of the `users` group by default. Required two API calls:

```bash
databricks api patch /api/2.0/permissions/database-instances/<inst> --json '{
  "access_control_list":[
    {"group_name":"users","permission_level":"CAN_USE"},
    {"service_principal_name":"<sp-1>","permission_level":"CAN_USE"},
    {"service_principal_name":"<sp-2>","permission_level":"CAN_USE"}
  ]}'
```

**Layer 2 — Postgres role for each SP:** even with `CAN_USE`, no Postgres
role gets auto-provisioned in this instance (the Lakebase auto-sync flow
does not appear to be enabled here). The original
`lakebase_grant_permissions.py` only granted `... TO PUBLIC`, which is a
no-op until a role for the SP exists. Tried adding explicit
`CREATE ROLE "<uuid>" IN ROLE databricks_users` — that silently failed
inside a `DO $$ ... END $$` block because **`databricks_users` does not
exist as a role on this instance** (verified via `pg_roles`). Switched to
plain `CREATE ROLE "<uuid>" WITH LOGIN` plus per-statement try/except in
Python (no DO block) so failures actually surface.

**Layer 3 — OAuth tokens don't validate against manually-created roles:**
even after `CREATE ROLE`, password auth still failed. Reason: `LakebasePool`
calls `WorkspaceClient.database.generate_database_credential()` to mint an
OAuth token and uses it as the Postgres password. Postgres on Lakebase only
accepts those tokens for **Lakebase-managed roles** (the
`databricks_writer_*` / `databricks_superuser` family). A role we
hand-crafted via `CREATE ROLE` has no auth-method hook, so it falls back to
SCRAM-SHA-256 against an empty password and fails. There is no documented
way (in this workspace) to mark a hand-created role as Lakebase-managed,
which forced the next layer.

**Layer 4 — PAT auth, same as the agent uses:** the agent's
`agent.py` already implements the workaround for Model Serving (where each
deploy creates a fresh ephemeral SP with no Postgres role). It reads
`LAKEBASE_PAT` from env and constructs
`WorkspaceClient(host, token=PAT)`, which then calls
`generate_database_credential` *as the PAT owner* (a real human user with a
real Lakebase-managed role). The showcase app needs the same path. This
required three sub-fixes:

1. **`showcase/backend.py`** — mirror the agent's pattern. **Important:**
   on Apps, `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` are
   auto-injected for the App SP, so `WorkspaceClient(host, token=PAT)`
   alone raises:

   ```
   validate: more than one authorization method configured: oauth and pat
   ```

   The fix is to construct an explicit `Config` and pin `auth_type="pat"`
   while also nulling the OAuth fields:

   ```python
   from databricks.sdk.config import Config
   cfg = Config(
       host=host,
       token=os.environ["LAKEBASE_PAT"],
       auth_type="pat",
       client_id=None,
       client_secret=None,
   )
   wc = WorkspaceClient(config=cfg)
   ```

2. **`showcase/deploy.sh`** — declare a `secret` resource in the rendered
   `app.yaml` and bind it to a `LAKEBASE_PAT` env var:

   ```yaml
   resources:
     - name: lakebase-pat
       secret:
         scope: ${LAKEBASE_PAT_SECRET_SCOPE}
         key:   ${LAKEBASE_PAT_SECRET_KEY}
         permission: READ

   env:
     - name: LAKEBASE_PAT
       valueFrom: lakebase-pat
   ```

3. **`apps update` is required to attach new resources** — `apps deploy`
   uploads source files and the `app.yaml` text, **but does not update the
   App's stored `resources:` array**. Result: the runtime emits
   `error resolving resource lakebase-pat for env LAKEBASE_PAT: resource lakebase-pat not found`
   even though the new yaml is present. Have to call:

   ```bash
   databricks apps update <name> --json @resources.json
   ```

   with the full updated resource list. Plus the App SP needs explicit
   `READ` on the secret scope (`databricks secrets put-acl <scope> <sp-id> READ`)
   — workspace-level secret-scope ACLs don't pass through automatically.

**Repo changes:**
- `deployment/lakebase_grant_permissions.py` — accept `APP_SP_CLIENT_IDS`
  widget; create roles per-SP without DO-block error swallowing.
- `deployment/deploy_lakebase_grants.sh` — auto-discover both apps' SP IDs.
- `showcase/backend.py` — PAT path mirroring `agent.py`, with
  `auth_type="pat"` to defeat OAuth auto-detection.
- `showcase/deploy.sh` — add `secret` resource + `valueFrom` env binding.
- New helper `deployment/force_create_app_sp_roles.py` and
  `deployment/verify_lakebase_state.py` — diagnostics that surface
  per-statement results so future failures aren't silent.

**README changes recommended:**
- Step 6 needs to spell out: workspace ACL → per-SP ACL → CREATE ROLE → PAT.
- Step 9/10 (deploy apps) needs a callout that `apps deploy` does not update
  resources; new `secret` resources must be applied via `apps update`.
- Add a note that the README's "no PAT needed on Apps" claim is workspace-
  dependent. Recommend always wiring the PAT path (matches the agent and
  works in any workspace).

### 3.7 `deploy.sh` was missing two top-level subcommands

`deploy.sh` dispatched only `agent`, `app`, `showcase`, `lakebase`,
`all-apps` — but the README references `bootstrap` (UC) and `grants` (PG).

**Fix:** Added both:

```bash
case "$1" in
  bootstrap) exec "$REPO_ROOT/deployment/deploy_bootstrap.sh" ;;
  grants)    exec "$REPO_ROOT/deployment/deploy_lakebase_grants.sh" ;;
  ...
esac
```

### 3.8 README naming mismatch on Model Serving endpoint

`agents.deploy()` derives the endpoint name from the registered model name
and **truncates** it to fit the 63-char Model Serving limit. The README and
`.env.example` imply `GTM_ENDPOINT` is whatever you set, but the apps and
agent integrations need the *actual* deployed endpoint name. After
`agents.deploy()` returned, the real name was
`agents_dolby_soundsight_catalog-gtm_agent-gtm_deal_intelligence`, not
whatever I'd put in `.env`.

**Fix (recommended for repo):** After `agents.deploy()` in
`log_and_deploy_notebook.py`, print the actual endpoint name to job output
and add a note in the README that `.env GTM_ENDPOINT` must be reconciled
post-deploy.

---

## 4. Workspace-specific Decisions (don't merge to repo — document for the customer)

These are choices I made to fit `fevm-dolby-soundsight`. They shouldn't change
the repo, but they should live somewhere the next operator on this workspace
can find them.

### 4.1 Reused existing infra instead of provisioning new

| Resource | Reused | Reason |
|---|---|---|
| Lakebase instance `dolby-portal-db` | Yes | Already provisioned for the dolby-platform-portal app; CU_1 is enough for memory |
| VS endpoint `soundsight-vs-endpoint` | Yes | Already warmed; saved 20–30 min provisioning |
| SQL warehouse `3f0ba1cfb2f640e6` | Yes | Existing serverless warehouse, already paid-for |
| UC catalog `dolby_soundsight_catalog` | Yes | Already existed; chose schema `gtm_agent` inside it |

This is why `setup/bootstrap_uc_objects.py` had to **remove** the
`CREATE CATALOG IF NOT EXISTS` statement — even with `IF NOT EXISTS`, the
metastore validates the catalog's storage root URL, and the existing
`dolby_soundsight_catalog` was created with a managed location that the
metastore validation didn't accept on re-run.

The repo should keep `CREATE CATALOG IF NOT EXISTS` for greenfield
deployments. This was a workspace-specific bypass.

### 4.2 Lakebase ACL grants

Granted directly to:

- `users` group: `CAN_USE` (per the README)
- `1adc66c5-fb67-4b0b-a91a-5c37194871b4` (mission-control SP): `CAN_USE`
- `47d91391-2416-4654-9321-abe3d598e60f` (gtm-deal-intelligence SP): `CAN_USE`

Both apps' SPs are not members of the `users` group (Apps SPs aren't, by
default in this workspace), so the group grant alone wasn't sufficient.

### 4.3 PAT-based Lakebase auth for Model Serving *and* the showcase App

The README claims the agent on Model Serving needs a PAT but the App SP
authenticates natively. **In this workspace, the App SP also needs PAT
auth** — because Lakebase did not auto-provision a Postgres role for the
SP, and any role we manually `CREATE ROLE`'d couldn't validate OAuth tokens
(see §3.6).

Wired the same `LAKEBASE_PAT` secret (`gtm-agent/lakebase-pat`) into the
showcase app via:

- `apps update mission-control --json @resources.json` to attach the new
  `secret` resource (deploy alone won't update resources)
- `secrets put-acl gtm-agent <mission-control-sp> READ` so the SP can read
  the secret at runtime

The PAT belongs to the deploying user (mine, `darien.hong@databricks.com`).
For longer-lived ownership, rotate to a workspace-owner SP's PAT.

### 4.4 `databricks_users` role does not exist on this Lakebase instance

When trying to `CREATE ROLE "<sp>" IN ROLE databricks_users`, the role
`databricks_users` is missing on `dolby-portal-db`. The `pg_roles`-visible
managed roles here are:

- `databricks_superuser` (the instance creator's superuser role)
- `databricks_writer_<numeric-id>` (auto-provisioned per workspace user)
- `gtm_agent_svc` (the native PG login we created for Model Serving fallback)

The new role-creation logic in `lakebase_grant_permissions.py` first checks
for `databricks_users` existence and only adds the IN ROLE clause if it
exists — keeping the script portable across instances that do/don't have
that group role.

### 4.5 LLM endpoint choices

Used Sonnet 4.6 for the agent and Haiku 4.5 for memory extraction. Both
are available as foundation-model endpoints in this workspace; no AI Gateway
external endpoint registration needed.

### 4.6 Workspace folder layout

```
/Workspace/Users/darien.hong@databricks.com/
├── gtm-deal-agent/              # agent + bootstrap notebooks
│   ├── agent.py
│   ├── log_and_deploy
│   ├── lakebase_memory_setup
│   ├── lakebase_grant_permissions
│   └── bootstrap_uc_objects
├── mission-control/             # showcase app source
└── gtm-deal-intelligence/       # main app source
```

These had to be `mkdirs`'d before any `workspace import` — `import` does not
auto-create parent folders.

---

## 5. Issue → Fix Quick-reference Table

| # | Symptom | Type | Fix |
|---|---|---|---|
| 1 | `refresh token is invalid` | env | `databricks auth login --profile ...` |
| 2 | `parent folder does not exist` | env | `databricks workspace mkdirs ...` |
| 3 | `Routine ... does not exist` (calculate_deal_health) | repo | New `bootstrap_uc_objects.py` notebook |
| 4 | `Metastore storage root URL does not exist` | env | Removed `CREATE CATALOG` (workspace-specific) |
| 5 | `WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED` | repo | Dropped `DEFAULT current_timestamp()` |
| 6 | `cannot import name 'ExecutionInfo' from 'langgraph.runtime'` | repo | Bumped `langgraph >= 1.1.7` |
| 7 | `GetFunction invalid full_name_arg` | repo | `os.environ[...] = ...` before `log_model` |
| 8 | `password authentication failed for user '<sp-uuid>'` (App → Lakebase) | repo | Wired `LAKEBASE_PAT` into showcase via secret resource + `apps update`; `auth_type="pat"` to defeat OAuth auto-detect — see §3.6 |
| 9 | `error resolving resource lakebase-pat for env LAKEBASE_PAT: resource lakebase-pat not found` | repo | `apps deploy` does not update resources; use `apps update --json` |
| 10 | `validate: more than one authorization method configured: oauth and pat` | repo | `Config(host, token, auth_type="pat", client_id=None, client_secret=None)` |
| 11 | `lakebase_grant_permissions.py` reports success but no SP roles created | repo | Removed `DO $$ ... END $$` wrapper that swallowed errors; added `databricks_users` existence check before IN ROLE |

(env = workspace setup; repo = should be PR'd back)

---

## 6. Recommended Repo PR

If you want to push these back upstream, the PR scope is:

```
deployment/log_and_deploy_notebook.py     ← env exports + langgraph/uc-langchain pins
deployment/deploy_agent.sh                ← langgraph >= 1.1.7
deployment/lakebase_grant_permissions.py  ← per-SP CREATE ROLE, no DO-block, databricks_users probe
deployment/deploy_lakebase_grants.sh      ← auto-discover App SPs
deployment/deploy_bootstrap.sh            ← new wrapper
deployment/force_create_app_sp_roles.py   ← diagnostic / fallback role-creation
deployment/verify_lakebase_state.py       ← Lakebase auth diagnostics
setup/bootstrap_uc_objects.py             ← new consolidated bootstrap
showcase/backend.py                       ← LAKEBASE_PAT path with auth_type="pat"
showcase/deploy.sh                        ← secret resource + valueFrom env binding
deploy.sh                                 ← bootstrap + grants subcommands
README.md                                 ← Step 6 (full Lakebase auth flow) + Step 8 + apps update note
```

The new `bootstrap_uc_objects.py` should keep `CREATE CATALOG IF NOT EXISTS`
for the greenfield case — only this `dolby-soundsight` deployment needed it
removed.

The README's Step 6 should be rewritten to reflect the actual working flow:
workspace ACL → per-SP ACL → Postgres role creation → **and the app must
also use the PAT path** (don't promise "no PAT needed on Apps" — it depends
on whether Lakebase auto-provisions roles in the target workspace, which is
not guaranteed).
