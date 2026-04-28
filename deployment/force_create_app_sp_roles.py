# Databricks notebook source
# MAGIC %md
# MAGIC # Force-create Postgres roles for App SPs (with verification)

# COMMAND ----------

dbutils.widgets.text("LAKEBASE_INSTANCE_NAME", "")
dbutils.widgets.text("DATABASE_NAME", "databricks_postgres")
dbutils.widgets.text("APP_SP_CLIENT_IDS", "")

LAKEBASE_INSTANCE_NAME = dbutils.widgets.get("LAKEBASE_INSTANCE_NAME")
DATABASE_NAME = dbutils.widgets.get("DATABASE_NAME") or "databricks_postgres"
APP_SP_CLIENT_IDS = [s.strip() for s in dbutils.widgets.get("APP_SP_CLIENT_IDS").split(",") if s.strip()]

assert LAKEBASE_INSTANCE_NAME
assert APP_SP_CLIENT_IDS, "Must pass APP_SP_CLIENT_IDS"

# COMMAND ----------

from databricks_ai_bridge.lakebase import LakebasePool
import re

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
for sp in APP_SP_CLIENT_IDS:
    assert UUID_RE.match(sp), f"Refusing to use SP id that is not a UUID: {sp!r}"

pool = LakebasePool(instance_name=LAKEBASE_INSTANCE_NAME)

results = []
def log(msg):
    print(msg)
    results.append(str(msg))

with pool.connection() as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT current_user, current_database();")
        log(f"Connected as: {cur.fetchone()}")

        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'databricks_users';")
        has_databricks_users = cur.fetchone() is not None
        log(f"databricks_users role exists: {has_databricks_users}")

        for sp in APP_SP_CLIENT_IDS:
            log(f"\n=== {sp} ===")
            cur.execute("SELECT rolname FROM pg_roles WHERE rolname = %s;", (sp,))
            existed = cur.fetchone() is not None
            log(f"  existed before: {existed}")

            if not existed:
                try:
                    cur.execute(f'CREATE ROLE "{sp}" WITH LOGIN;')
                    log("  CREATE ROLE: OK")
                except Exception as e:
                    log(f"  CREATE ROLE: FAILED -> {e}")
                    continue

            if has_databricks_users:
                try:
                    cur.execute(f'GRANT databricks_users TO "{sp}";')
                    log("  GRANT databricks_users: OK")
                except Exception as e:
                    log(f"  GRANT databricks_users: FAILED -> {e}")

            for stmt, label in [
                (f'GRANT CONNECT ON DATABASE "{DATABASE_NAME}" TO "{sp}";', "CONNECT on db"),
                (f'GRANT USAGE, CREATE ON SCHEMA public TO "{sp}";', "USAGE+CREATE on public"),
                (f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{sp}";', "ALL on public tables"),
                (f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{sp}";', "ALL on public sequences"),
                (f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{sp}";', "default ALL on tables"),
                (f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "{sp}";', "default ALL on sequences"),
            ]:
                try:
                    cur.execute(stmt)
                    log(f"  {label}: OK")
                except Exception as e:
                    log(f"  {label}: FAILED -> {e}")

            cur.execute(
                "SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname = %s;", (sp,)
            )
            row = cur.fetchone()
            log(f"  exists after: {row}")

dbutils.notebook.exit("\n".join(results))
