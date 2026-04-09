"""
06 · Lakewatch — Security detection rules for the GTM agent.

Run as a Databricks notebook. Requires:
  - Lakewatch enabled on the workspace
  - MLflow traces flowing to system tables
"""

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  RULE 1: Contact PII in agent output (data exfiltration)                ║
# ╚══════════════════════════════════════════════════════════════════════════╝

RULE_1_QUERY = """
SELECT
    trace_id,
    request.user_id AS ae_id,
    response.output_text,
    trace_timestamp
FROM system.serving.served_requests
WHERE serving_endpoint_name = 'gtm-deal-intelligence'
  AND trace_timestamp > CURRENT_TIMESTAMP - INTERVAL 1 HOUR
  AND response.output_text RLIKE '\\\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Z|a-z]{2,}\\\\b'
  AND LENGTH(response.output_text) > 2000
"""

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  RULE 2: Prompt injection detection                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝

RULE_2_QUERY = """
SELECT
    trace_id,
    request.user_id AS ae_id,
    request.input_text AS user_input,
    trace_timestamp
FROM system.serving.served_requests
WHERE serving_endpoint_name = 'gtm-deal-intelligence'
  AND trace_timestamp > CURRENT_TIMESTAMP - INTERVAL 15 MINUTES
  AND (
    LOWER(request.input_text) LIKE '%ignore previous instructions%'
    OR LOWER(request.input_text) LIKE '%ignore all prior%'
    OR LOWER(request.input_text) LIKE '%system prompt%'
    OR LOWER(request.input_text) LIKE '%reveal your instructions%'
    OR LOWER(request.input_text) LIKE '%act as%root%'
    OR LOWER(request.input_text) LIKE '%pretend you are%'
    OR LOWER(request.input_text) LIKE '%disregard%instructions%'
  )
"""

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  RULE 3: Unusual outreach volume spike                                  ║
# ╚══════════════════════════════════════════════════════════════════════════╝

RULE_3_QUERY = """
WITH daily_baseline AS (
    SELECT
        ae_id,
        AVG(daily_count) AS avg_daily,
        STDDEV(daily_count) AS std_daily
    FROM (
        SELECT ae_id, DATE(created_at) AS log_date, COUNT(*) AS daily_count
        FROM gtm.crm.outreach_log
        WHERE created_at > CURRENT_DATE - 30
        GROUP BY ae_id, DATE(created_at)
    )
    GROUP BY ae_id
),
today_count AS (
    SELECT ae_id, COUNT(*) AS today_count
    FROM gtm.crm.outreach_log
    WHERE DATE(created_at) = CURRENT_DATE
    GROUP BY ae_id
)
SELECT t.ae_id, t.today_count, b.avg_daily
FROM today_count t
JOIN daily_baseline b ON t.ae_id = b.ae_id
WHERE t.today_count > GREATEST(b.avg_daily * 10, 50)
"""

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  RULE 4: Broad account data access (potential scraping)                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝

RULE_4_QUERY = """
SELECT
    ae_id,
    COUNT(DISTINCT account_id) AS accounts_accessed,
    MIN(accessed_at) AS first_access,
    MAX(accessed_at) AS last_access
FROM gtm.audit.audit_agent_access
WHERE accessed_at > CURRENT_TIMESTAMP - INTERVAL 1 HOUR
GROUP BY ae_id
HAVING COUNT(DISTINCT account_id) > 20
"""

# ---------------------------------------------------------------------------
# Register rules via SQL (Lakewatch API — adapt to your workspace setup)
# ---------------------------------------------------------------------------
# Note: Lakewatch rule creation is workspace-specific. The queries above
# can be registered as:
#   1. Databricks SQL Alerts (available today)
#   2. Lakewatch detection rules (when API is GA)
#
# For the demo, create SQL Alerts:

ALERT_CONFIGS = [
    {
        "name": "GTM Agent: PII in Output",
        "query": RULE_1_QUERY,
        "schedule": "0 */1 * * *",  # Every hour
        "condition": "ROWS > 0",
        "description": "Detects when agent output contains email PII patterns — potential data exfiltration.",
    },
    {
        "name": "GTM Agent: Prompt Injection",
        "query": RULE_2_QUERY,
        "schedule": "*/15 * * * *",  # Every 15 min
        "condition": "ROWS > 0",
        "description": "Detects prompt injection attempts in user inputs to the GTM agent.",
    },
    {
        "name": "GTM Agent: Outreach Volume Spike",
        "query": RULE_3_QUERY,
        "schedule": "0 */4 * * *",  # Every 4 hours
        "condition": "ROWS > 0",
        "description": "Alerts when a single AE generates 10x their normal daily outreach volume.",
    },
    {
        "name": "GTM Agent: Broad Account Scraping",
        "query": RULE_4_QUERY,
        "schedule": "0 */1 * * *",
        "condition": "ROWS > 0",
        "description": "Detects when an AE accesses 20+ accounts in one hour — potential data scraping.",
    },
]

print("Lakewatch / SQL Alert configurations generated.")
print("Register these queries as SQL Alerts in your Databricks workspace.")
for i, cfg in enumerate(ALERT_CONFIGS, 1):
    print(f"\n  Rule {i}: {cfg['name']}")
    print(f"  Schedule: {cfg['schedule']}")
    print(f"  Description: {cfg['description']}")
