# Databricks notebook source
# MAGIC %md
# MAGIC # Grant Lakebase Postgres Permissions
# MAGIC
# MAGIC Grants Postgres-level permissions to the Model Serving SP and Databricks Apps SPs
# MAGIC so they can connect to the `gtm-agent-memory` Lakebase instance.

# COMMAND ----------

LAKEBASE_INSTANCE_NAME = "gtm-agent-memory"

# SPs that need access:
# - aa2d81aa-936a-4cf2-bd4b-96a0c2b0ff55 = agents.deploy() auto-generated SP (from Model Serving logs)
# - 51ace28c-7b7d-4396-b41d-225d404b9bd2 = gtm-deal-intelligence app SP
# - 0d4d9c11-2fc5-4617-b6c3-71cbfa6b7138 = mission-control app SP

PRINCIPALS = [
    "aa2d81aa-936a-4cf2-bd4b-96a0c2b0ff55",
    "51ace28c-7b7d-4396-b41d-225d404b9bd2",
    "0d4d9c11-2fc5-4617-b6c3-71cbfa6b7138",
]

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
import psycopg

pool = LakebasePool(instance_name=LAKEBASE_INSTANCE_NAME)

# Create a pg_native_login service account for Model Serving
# (agents.deploy() creates a NEW invisible SP per model version, so Databricks-auth fails)
PG_SVC_USER = "gtm_agent_svc"
PG_SVC_PASSWORD = "LakebaseGTM2026!"

try:
    with pool.connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"DO $$ BEGIN CREATE ROLE {PG_SVC_USER} LOGIN PASSWORD '{PG_SVC_PASSWORD}'; EXCEPTION WHEN duplicate_object THEN ALTER ROLE {PG_SVC_USER} PASSWORD '{PG_SVC_PASSWORD}'; END $$;")
            cur.execute(f"GRANT CONNECT ON DATABASE databricks_postgres TO {PG_SVC_USER};")
            cur.execute(f"GRANT USAGE, CREATE ON SCHEMA public TO {PG_SVC_USER};")
            cur.execute(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {PG_SVC_USER};")
            cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {PG_SVC_USER};")
            cur.execute(f"GRANT databricks_superuser TO {PG_SVC_USER};")
            print(f"Created pg_native_login user: {PG_SVC_USER}")
except Exception as e:
    print(f"Failed to create service user: {e}")

# Also grant PUBLIC for any Databricks-authenticated connections
try:
    with pool.connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("GRANT CONNECT ON DATABASE databricks_postgres TO PUBLIC;")
            cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO PUBLIC;")
            cur.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO PUBLIC;")
            cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO PUBLIC;")
            print("Granted PUBLIC access")
except Exception as e:
    print(f"Failed to grant PUBLIC: {e}")

print("\nDone!")
