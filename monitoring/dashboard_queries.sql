-- ============================================================================
-- Monitoring Dashboard Queries
-- ============================================================================
-- Use these in a Databricks SQL Dashboard for ongoing GTM agent observability.
-- Databricks tech: DBSQL Dashboards + MLflow system tables + Lakebase
-- ============================================================================

-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  1. Agent Usage — Daily invocations and unique AEs                      ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

SELECT
    DATE(request_time) AS date,
    COUNT(*) AS total_invocations,
    COUNT(DISTINCT request.user_id) AS unique_aes,
    ROUND(AVG(response_time_ms), 0) AS avg_latency_ms,
    ROUND(PERCENTILE(response_time_ms, 0.95), 0) AS p95_latency_ms
FROM system.serving.served_requests
WHERE serving_endpoint_name = 'gtm-deal-intelligence'
  AND request_time > CURRENT_DATE - 30
GROUP BY DATE(request_time)
ORDER BY date DESC;


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  2. Agent Quality — Evaluation scores over time                         ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

SELECT
    DATE(r.end_time) AS eval_date,
    r.run_name,
    MAX(CASE WHEN m.key = 'groundedness/mean' THEN m.value END) AS groundedness,
    MAX(CASE WHEN m.key = 'relevance/mean' THEN m.value END) AS relevance,
    MAX(CASE WHEN m.key = 'personalization_quality/mean' THEN m.value END) AS personalization,
    MAX(CASE WHEN m.key = 'safety/mean' THEN m.value END) AS safety
FROM system.ml.model_training_runs r
JOIN system.ml.model_training_metrics m ON r.run_id = m.run_id
WHERE r.experiment_name = '/gtm/deal-intelligence-eval'
GROUP BY DATE(r.end_time), r.run_name
ORDER BY eval_date DESC;


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  3. Tool Usage — Which tools are called most frequently                 ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

SELECT
    tool_called,
    COUNT(*) AS call_count,
    COUNT(DISTINCT ae_id) AS unique_aes,
    COUNT(DISTINCT opp_id) AS unique_opps
FROM gtm.audit.audit_agent_access
WHERE accessed_at > CURRENT_DATE - 7
GROUP BY tool_called
ORDER BY call_count DESC;


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  4. Memory Growth — Long-term memory accumulation                       ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

SELECT
    'AE Preferences' AS memory_type,
    COUNT(*) AS total_records,
    COUNT(DISTINCT ae_id) AS unique_aes
FROM gtm.crm.outreach_log  -- Placeholder: replace with memory table when accessible
UNION ALL
SELECT
    'Account Context',
    0, 0  -- Replace with: SELECT COUNT(*), COUNT(DISTINCT account_id) FROM gtm.memory_account_context
UNION ALL
SELECT
    'Deal Decisions',
    0, 0; -- Replace with: SELECT COUNT(*), COUNT(DISTINCT opp_id) FROM gtm.memory_deal_decisions


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  5. Outreach Effectiveness — Drafts generated vs approved vs sent       ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

SELECT
    DATE(created_at) AS date,
    COUNT(*) AS drafts_generated,
    SUM(CASE WHEN approved THEN 1 ELSE 0 END) AS approved,
    SUM(CASE WHEN sent_at IS NOT NULL THEN 1 ELSE 0 END) AS sent,
    ROUND(SUM(CASE WHEN approved THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS approval_rate_pct
FROM gtm.crm.outreach_log
WHERE created_at > CURRENT_DATE - 30
GROUP BY DATE(created_at)
ORDER BY date DESC;


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  6. Security — Lakewatch alert summary                                  ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

-- Replace with actual Lakewatch alert table when available
SELECT
    'Prompt Injection' AS alert_type,
    0 AS alerts_last_7d,
    0 AS alerts_last_30d
UNION ALL
SELECT 'PII Exfiltration', 0, 0
UNION ALL
SELECT 'Volume Spike', 0, 0
UNION ALL
SELECT 'Broad Scraping', 0, 0;
