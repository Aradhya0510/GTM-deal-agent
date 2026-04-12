# Databricks notebook source
# 07 · Create audit table for agent security events

spark.sql("""
CREATE TABLE IF NOT EXISTS users.aradhya_chouhan.audit_agent_access (
    event_id        STRING      NOT NULL,
    event_type      STRING      NOT NULL,
    ae_id           STRING,
    thread_id       STRING,
    detail          STRING,
    created_at      TIMESTAMP
)
USING DELTA
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true'
)
COMMENT 'Audit log for GTM agent — security events and tool access tracking'
""")

print("audit_agent_access table created successfully.")
