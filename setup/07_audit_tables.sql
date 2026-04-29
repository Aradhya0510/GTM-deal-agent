-- 07 · Audit table for agent security events and tool access logging
-- Run on: e2-demo-west.cloud.databricks.com
-- Catalog: users | Schema: aradhya_chouhan

USE CATALOG users;
USE SCHEMA aradhya_chouhan;

-- Note: created_at has NO Delta DEFAULT clause. Delta column defaults require
-- enabling 'delta.feature.allowColumnDefaults' in TBLPROPERTIES, which causes
-- WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED on workspaces that don't
-- enable that feature. The agent's audit-write path passes current_timestamp()
-- explicitly in every INSERT, so the default is unused — safer to drop it.
CREATE TABLE IF NOT EXISTS audit_agent_access (
    event_id        STRING      NOT NULL,
    event_type      STRING      NOT NULL,   -- 'tool_call', 'prompt_injection_blocked', 'pii_in_output'
    ae_id           STRING,
    thread_id       STRING,
    detail          STRING,                 -- tool name, input snippet, or PII types found
    created_at      TIMESTAMP
)
USING DELTA
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true'
)
COMMENT 'Audit log for GTM agent — security events and tool access tracking';
