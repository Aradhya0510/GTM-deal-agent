# Databricks notebook source
# MAGIC %md
# MAGIC # Grant Lakebase Postgres Permissions
# MAGIC
# MAGIC Grants Postgres-level permissions to Model Serving and Databricks Apps SPs
# MAGIC so they can connect to the Lakebase instance.

# COMMAND ----------

dbutils.widgets.text("LAKEBASE_INSTANCE_NAME", "")
dbutils.widgets.text("DATABASE_NAME", "databricks_postgres")
dbutils.widgets.text("PG_SVC_USER", "gtm_agent_svc")
dbutils.widgets.text("PG_SVC_PASSWORD", "LakebaseGTM2026!")
dbutils.widgets.text("APP_SP_CLIENT_IDS", "")

LAKEBASE_INSTANCE_NAME = dbutils.widgets.get("LAKEBASE_INSTANCE_NAME")
DATABASE_NAME = dbutils.widgets.get("DATABASE_NAME") or "databricks_postgres"
PG_SVC_USER = dbutils.widgets.get("PG_SVC_USER") or "gtm_agent_svc"
PG_SVC_PASSWORD = dbutils.widgets.get("PG_SVC_PASSWORD") or "LakebaseGTM2026!"
APP_SP_CLIENT_IDS = [s.strip() for s in dbutils.widgets.get("APP_SP_CLIENT_IDS").split(",") if s.strip()]

assert LAKEBASE_INSTANCE_NAME, "LAKEBASE_INSTANCE_NAME widget must be set"
print(f"Granting on Lakebase instance: {LAKEBASE_INSTANCE_NAME}, database: {DATABASE_NAME}")
print(f"App SP client IDs: {APP_SP_CLIENT_IDS}")

# COMMAND ----------

from databricks_langchain import DatabricksStore, CheckpointSaver

store = DatabricksStore(
    instance_name=LAKEBASE_INSTANCE_NAME,
    embedding_endpoint="databricks-gte-large-en",
    embedding_dims=1024,
)

# Run setup to create the store tables (as superuser)
store.setup()
print("DatabricksStore tables created/verified")

cp = CheckpointSaver(instance_name=LAKEBASE_INSTANCE_NAME)
cp.setup()
print("CheckpointSaver tables created/verified")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Grant Postgres permissions to SPs
# MAGIC
# MAGIC The `databricks_superuser` (instance creator) needs to grant:
# MAGIC - CONNECT on database
# MAGIC - USAGE + CREATE on schema
# MAGIC - ALL on tables

# COMMAND ----------

from databricks_ai_bridge.lakebase import LakebasePool

pool = LakebasePool(instance_name=LAKEBASE_INSTANCE_NAME)

# Create a pg_native_login service account for Model Serving.
# (agents.deploy() creates a NEW invisible SP per model version, so OAuth fails.)
try:
    with pool.connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                f"DO $$ BEGIN CREATE ROLE {PG_SVC_USER} LOGIN PASSWORD '{PG_SVC_PASSWORD}'; "
                f"EXCEPTION WHEN duplicate_object THEN ALTER ROLE {PG_SVC_USER} PASSWORD '{PG_SVC_PASSWORD}'; "
                f"END $$;"
            )
            cur.execute(f'GRANT CONNECT ON DATABASE "{DATABASE_NAME}" TO {PG_SVC_USER};')
            cur.execute(f"GRANT USAGE, CREATE ON SCHEMA public TO {PG_SVC_USER};")
            cur.execute(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {PG_SVC_USER};")
            cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {PG_SVC_USER};")
            cur.execute(f"GRANT databricks_superuser TO {PG_SVC_USER};")
            print(f"Created pg_native_login user: {PG_SVC_USER}")
except Exception as e:
    print(f"Failed to create service user: {e}")

# Grant PUBLIC for any Databricks-authenticated identities (including App SPs).
try:
    with pool.connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'GRANT CONNECT ON DATABASE "{DATABASE_NAME}" TO PUBLIC;')
            cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO PUBLIC;")
            cur.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO PUBLIC;")
            cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO PUBLIC;")
            print("Granted PUBLIC access")
except Exception as e:
    print(f"Failed to grant PUBLIC: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create explicit Postgres roles for App Service Principals
# MAGIC
# MAGIC Databricks Apps SPs authenticate to Lakebase via OAuth tokens, but Postgres still
# MAGIC needs a matching role to exist before it can validate the token. CAN_USE on the
# MAGIC instance + PUBLIC grants is not enough — we must `CREATE ROLE` for each SP UUID.
# MAGIC The role is created with LOGIN; Lakebase validates the OAuth token at connect
# MAGIC time, not via a stored password.

# COMMAND ----------

if APP_SP_CLIENT_IDS:
    try:
        with pool.connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                for sp_id in APP_SP_CLIENT_IDS:
                    role = sp_id  # Postgres role name = SP UUID (quoted)
                    cur.execute(
                        f"DO $$ BEGIN "
                        f"  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
                        f"    CREATE ROLE \"{role}\" WITH LOGIN IN ROLE databricks_users; "
                        f"  END IF; "
                        f"END $$;"
                    )
                    cur.execute(f'GRANT CONNECT ON DATABASE "{DATABASE_NAME}" TO "{role}";')
                    cur.execute(f'GRANT USAGE, CREATE ON SCHEMA public TO "{role}";')
                    cur.execute(f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{role}";')
                    cur.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{role}";')
                    print(f"Provisioned Postgres role for App SP: {sp_id}")
    except Exception as e:
        print(f"Failed to provision App SP roles: {e}")
else:
    print("No APP_SP_CLIENT_IDS provided — skipping per-SP role creation")

print("\nDone!")
