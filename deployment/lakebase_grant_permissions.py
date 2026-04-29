# Databricks notebook source
# MAGIC %md
# MAGIC # Grant Lakebase Postgres Permissions
# MAGIC
# MAGIC Sets up Postgres-level permissions on the Lakebase instance so the
# MAGIC agent (Model Serving) and Streamlit apps (Databricks Apps) can connect.
# MAGIC
# MAGIC What this notebook does:
# MAGIC 1. Calls `DatabricksStore.setup()` and `CheckpointSaver.setup()` so the
# MAGIC    memory tables exist (idempotent — safe to re-run).
# MAGIC 2. Probes `pg_roles` for the `databricks_users` group role, which exists
# MAGIC    on some Lakebase instances and not others. The script only adds an
# MAGIC    `IN ROLE databricks_users` clause to subsequent `CREATE ROLE`
# MAGIC    statements when that role exists.
# MAGIC 3. For each Databricks App service principal client ID supplied via
# MAGIC    `APP_SP_CLIENT_IDS`, creates a Postgres role and grants
# MAGIC    `CONNECT` / `USAGE` / table privileges on the public schema.
# MAGIC 4. Best-effort `GRANT ... TO PUBLIC` to handle workspaces where the
# MAGIC    auto-provisioned `databricks_writer_*` family covers the App SP
# MAGIC    natively.
# MAGIC
# MAGIC Important: every SQL statement is wrapped in Python `try/except` (one
# MAGIC statement at a time, no `DO $$ ... END $$` blocks). The original script
# MAGIC swallowed errors inside DO blocks, so failures like "role
# MAGIC `databricks_users` does not exist" looked like success. This rewrite
# MAGIC surfaces every result with `[OK]` / `[FAIL: <msg>]` per statement.
# MAGIC
# MAGIC Caveat (CLAUDE.md learning #21 / Darien's §3.6 layer 3): on workspaces
# MAGIC where Lakebase does NOT auto-provision a `databricks_writer_<id>` role
# MAGIC for the App SP, OAuth tokens minted by
# MAGIC `WorkspaceClient.database.generate_database_credential()` may still
# MAGIC fail to validate against a hand-created role. In those cases the App
# MAGIC must fall back to PAT auth (handled in `showcase/backend.py`).

# COMMAND ----------

# ── Configuration via notebook widgets ──
# When run as a job, deployment/deploy_lakebase_grants.sh populates these from
# .env (auto-discovering APP_SP_CLIENT_IDS via `databricks apps get`).
# When run interactively, set the widget values in the notebook UI.
dbutils.widgets.text("LAKEBASE_INSTANCE_NAME", "")
dbutils.widgets.text("DATABASE_NAME", "databricks_postgres")
dbutils.widgets.text(
    "APP_SP_CLIENT_IDS", "",
    "Comma-separated App SP client UUIDs (auto-populated by deploy_lakebase_grants.sh)",
)
dbutils.widgets.text("DATABRICKS_EMBEDDING_ENDPOINT", "databricks-gte-large-en")

LAKEBASE_INSTANCE_NAME = dbutils.widgets.get("LAKEBASE_INSTANCE_NAME")
DATABASE_NAME = dbutils.widgets.get("DATABASE_NAME")
EMBEDDING_ENDPOINT = dbutils.widgets.get("DATABRICKS_EMBEDDING_ENDPOINT")
APP_SP_CLIENT_IDS = [
    s.strip()
    for s in dbutils.widgets.get("APP_SP_CLIENT_IDS").split(",")
    if s.strip()
]

assert LAKEBASE_INSTANCE_NAME, "LAKEBASE_INSTANCE_NAME widget must be set"

print(f"Lakebase instance:      {LAKEBASE_INSTANCE_NAME}")
print(f"Database:               {DATABASE_NAME}")
print(f"App SPs to grant:       {len(APP_SP_CLIENT_IDS)}")
for sp in APP_SP_CLIENT_IDS:
    print(f"                          - {sp}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Memory tables (`DatabricksStore.setup()` + `CheckpointSaver.setup()`)
# MAGIC
# MAGIC These calls run as the notebook user (the `databricks_superuser` who
# MAGIC owns the instance), so they have permission to CREATE TABLE in the
# MAGIC public schema. Idempotent.

# COMMAND ----------

from databricks_langchain import DatabricksStore, CheckpointSaver

store = DatabricksStore(
    instance_name=LAKEBASE_INSTANCE_NAME,
    embedding_endpoint=EMBEDDING_ENDPOINT,
    embedding_dims=1024,
)
store.setup()
print("  [OK] DatabricksStore tables created/verified")

cp = CheckpointSaver(instance_name=LAKEBASE_INSTANCE_NAME)
cp.setup()
print("  [OK] CheckpointSaver tables created/verified")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Set up a single-statement SQL helper
# MAGIC
# MAGIC One connection, autocommit on, one cursor per statement. Returns the
# MAGIC error so the caller can branch on "already exists" vs unexpected
# MAGIC failures, instead of swallowing everything.

# COMMAND ----------

from databricks_ai_bridge.lakebase import LakebasePool

pool = LakebasePool(instance_name=LAKEBASE_INSTANCE_NAME)


def run_sql(sql, label=None, fetch=False):
    """Execute one SQL statement. Surface success/failure explicitly.

    Returns:
      - For fetch=True: list of rows on success, None on failure
      - For fetch=False: None on success, the Exception on failure
    """
    label = label or sql.split("\n")[0][:70]
    try:
        with pool.connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql)
                if fetch:
                    rows = cur.fetchall()
                    print(f"  [OK]   {label}  ({len(rows)} rows)")
                    return rows
                print(f"  [OK]   {label}")
                return None
    except Exception as e:
        msg = str(e).strip().splitlines()[0][:200]
        print(f"  [FAIL] {label}  -> {msg}")
        return e if not fetch else None

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Probe for `databricks_users` role
# MAGIC
# MAGIC On some Lakebase instances `databricks_users` is a parent group role.
# MAGIC If it exists, hand-created roles can `IN ROLE databricks_users` and
# MAGIC inherit grants. If it doesn't, including that clause causes a hard
# MAGIC `role "databricks_users" does not exist` failure that breaks the rest
# MAGIC of the script. Probe first, decide later.

# COMMAND ----------

rows = run_sql(
    "SELECT 1 FROM pg_roles WHERE rolname = 'databricks_users'",
    label="probe pg_roles for databricks_users",
    fetch=True,
)
HAS_DB_USERS = bool(rows)
print(f"  databricks_users role exists: {HAS_DB_USERS}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Per-SP Postgres role creation
# MAGIC
# MAGIC Each Databricks App has a stable service principal whose `client_id`
# MAGIC (UUID) is the Postgres role name. We create the role with `LOGIN`,
# MAGIC optionally chain it under `databricks_users`, then grant the
# MAGIC connect/usage/select privileges on the public schema where the memory
# MAGIC tables live.

# COMMAND ----------

if not APP_SP_CLIENT_IDS:
    print("  No APP_SP_CLIENT_IDS provided — skipping per-SP role creation.")
    print("  (deploy_lakebase_grants.sh auto-discovers SP IDs from your apps;")
    print("  if you have no Databricks Apps that need Lakebase access, this")
    print("  is fine — Model Serving uses LAKEBASE_PAT auth instead.)")

for sp_id in APP_SP_CLIENT_IDS:
    in_role = " IN ROLE databricks_users" if HAS_DB_USERS else ""
    sql = f'CREATE ROLE "{sp_id}" WITH LOGIN{in_role}'
    err = run_sql(sql, label=f'CREATE ROLE "{sp_id}"')
    if err and "already exists" not in str(err).lower():
        print(f"           Role creation may have failed for unexpected reasons.")
        print(f"           Continuing with grants — they're idempotent.")

    run_sql(
        f'GRANT CONNECT ON DATABASE {DATABASE_NAME} TO "{sp_id}"',
        label=f'GRANT CONNECT to "{sp_id}"',
    )
    run_sql(
        f'GRANT USAGE ON SCHEMA public TO "{sp_id}"',
        label=f'GRANT USAGE on schema public to "{sp_id}"',
    )
    run_sql(
        f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{sp_id}"',
        label=f'GRANT ALL TABLES to "{sp_id}"',
    )
    run_sql(
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{sp_id}"',
        label=f'ALTER DEFAULT for "{sp_id}"',
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Best-effort PUBLIC grants
# MAGIC
# MAGIC On workspaces that auto-provision `databricks_writer_<id>` for every
# MAGIC user, granting to PUBLIC covers them transitively. Harmless on
# MAGIC workspaces where the per-SP grants above already did the work.

# COMMAND ----------

run_sql(
    f"GRANT CONNECT ON DATABASE {DATABASE_NAME} TO PUBLIC",
    label="GRANT CONNECT to PUBLIC",
)
run_sql(
    "GRANT USAGE ON SCHEMA public TO PUBLIC",
    label="GRANT USAGE on schema public to PUBLIC",
)
run_sql(
    "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO PUBLIC",
    label="GRANT ALL TABLES to PUBLIC",
)
run_sql(
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO PUBLIC",
    label="ALTER DEFAULT for PUBLIC",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Verification — list roles and their privileges
# MAGIC
# MAGIC Quick check so the job log shows the post-state. Helpful when something
# MAGIC went wrong: you can see which roles exist and what grants they have.

# COMMAND ----------

print("Roles whose names match an App SP UUID or are databricks_*:")
run_sql(
    """
    SELECT rolname, rolcanlogin, rolcreatedb, rolsuper
    FROM pg_roles
    WHERE rolname LIKE 'databricks_%'
       OR rolname ~ '^[0-9a-f-]{36}$'
    ORDER BY rolname
    """,
    label="pg_roles snapshot",
    fetch=True,
)

# COMMAND ----------

print("\n  Lakebase grants complete.")
print(f"  Per-SP roles processed: {len(APP_SP_CLIENT_IDS)}")
print(f"  databricks_users present: {HAS_DB_USERS}")
print()
print("  Reminder: if your App SP can't authenticate with these grants because")
print("  of CLAUDE.md learning #21 (manually-created roles can't validate")
print("  OAuth tokens on some instances), the App falls back to LAKEBASE_PAT")
print("  auth — see deployment/agent.py and showcase/backend.py.")

dbutils.notebook.exit(f"Grants applied to {LAKEBASE_INSTANCE_NAME}")
