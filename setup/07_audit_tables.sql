-- 07 · Audit table for agent security events and tool access logging
-- Run on: e2-demo-west.cloud.databricks.com
-- Catalog: users | Schema: aradhya_chouhan

USE CATALOG users;
USE SCHEMA aradhya_chouhan;

CREATE TABLE IF NOT EXISTS audit_agent_access (
    event_id        STRING      NOT NULL,
    event_type      STRING      NOT NULL,   -- 'tool_call', 'prompt_injection_blocked', 'pii_in_output'
    ae_id           STRING,
    thread_id       STRING,
    detail          STRING,                 -- tool name, input snippet, or PII types found
    created_at      TIMESTAMP   DEFAULT current_timestamp()
)
USING DELTA
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true'
)
COMMENT 'Audit log for GTM agent — security events and tool access tracking';
