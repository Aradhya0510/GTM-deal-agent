# Databricks notebook source
# MAGIC %md
# MAGIC # Verify Lakebase Postgres State
# MAGIC
# MAGIC Direct verification: are the App SP roles actually in pg_roles?
# MAGIC What grants do they have? What does pg_hba look like?

# COMMAND ----------

dbutils.widgets.text("LAKEBASE_INSTANCE_NAME", "")
dbutils.widgets.text("DATABASE_NAME", "databricks_postgres")
dbutils.widgets.text("APP_SP_CLIENT_IDS", "")

LAKEBASE_INSTANCE_NAME = dbutils.widgets.get("LAKEBASE_INSTANCE_NAME")
DATABASE_NAME = dbutils.widgets.get("DATABASE_NAME") or "databricks_postgres"
APP_SP_CLIENT_IDS = [s.strip() for s in dbutils.widgets.get("APP_SP_CLIENT_IDS").split(",") if s.strip()]

assert LAKEBASE_INSTANCE_NAME

# COMMAND ----------

from databricks_ai_bridge.lakebase import LakebasePool

pool = LakebasePool(instance_name=LAKEBASE_INSTANCE_NAME)

lines = []
def log(msg):
    print(msg)
    lines.append(str(msg))

with pool.connection() as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT current_user, current_database();")
        log(f"WHO AM I: {cur.fetchone()}")

        log("\n--- pg_roles matching App SPs ---")
        for sp in APP_SP_CLIENT_IDS:
            cur.execute(
                "SELECT rolname, rolcanlogin, rolinherit, rolconnlimit "
                "FROM pg_roles WHERE rolname = %s;", (sp,)
            )
            row = cur.fetchone()
            log(f"  {sp}: {row}")

        log("\n--- All non-system roles ---")
        cur.execute(
            "SELECT rolname FROM pg_roles "
            "WHERE rolname NOT LIKE 'pg_%' AND rolname NOT LIKE 'rds_%' "
            "ORDER BY rolname;"
        )
        for (r,) in cur.fetchall():
            log(f"  {r}")

        log(f"\n--- DATABASE-level grants on {DATABASE_NAME} ---")
        cur.execute("SELECT datacl FROM pg_database WHERE datname = %s;", (DATABASE_NAME,))
        log(f"  datacl: {cur.fetchone()}")

        log("\n--- SCHEMA-level grants on public ---")
        cur.execute("SELECT nspacl FROM pg_namespace WHERE nspname = 'public';")
        log(f"  nspacl: {cur.fetchone()}")

        log("\n--- Memberships of App SP roles ---")
        for sp in APP_SP_CLIENT_IDS:
            cur.execute(
                "SELECT r.rolname AS member_of "
                "FROM pg_auth_members am "
                "JOIN pg_roles r ON r.oid = am.roleid "
                "JOIN pg_roles m ON m.oid = am.member "
                "WHERE m.rolname = %s;", (sp,)
            )
            rows = [r[0] for r in cur.fetchall()]
            log(f"  {sp} is member of: {rows}")

dbutils.notebook.exit("\n".join(lines))
