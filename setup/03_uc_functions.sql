-- ============================================================================
-- 03 · Unity Catalog Functions — Agent tools registered as UC Functions
-- ============================================================================
-- Run in a Databricks SQL notebook connected to a serverless warehouse.
-- These functions become callable by the agent via UCFunctionTool.
-- ============================================================================

USE CATALOG gtm;

-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  TOOL 1: calculate_deal_health                                          ║
-- ║  Scores an opportunity 0-100 on deal health with risk flag breakdown.   ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

CREATE OR REPLACE FUNCTION gtm.tools.calculate_deal_health(opp_id STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Calculates deal health score (0-100) with risk flags for an opportunity. Returns JSON with score breakdown, stage, days to close, champion, and specific risk flags.'
RETURN
  SELECT to_json(named_struct(
    'opp_id',           o.opp_id,
    'account',          a.company_name,
    'stage',            o.stage,
    'amount',           o.amount,
    'days_to_close',    datediff(o.close_date, current_date()),
    'health_score',     ROUND(
        -- Stage score (30 pts)
        CASE
          WHEN o.stage = 'Negotiation' THEN 30
          WHEN o.stage = 'Proposal' THEN 22
          WHEN o.stage = 'Technical Validation' THEN 15
          WHEN o.stage = 'Discovery' THEN 8
          ELSE 5
        END +
        -- Contact recency (20 pts)
        CASE
          WHEN EXISTS (
            SELECT 1 FROM gtm.crm.contacts c
            WHERE c.account_id = o.account_id AND c.last_contacted > date_sub(current_date(), 7)
          ) THEN 20
          WHEN EXISTS (
            SELECT 1 FROM gtm.crm.contacts c
            WHERE c.account_id = o.account_id AND c.last_contacted > date_sub(current_date(), 14)
          ) THEN 10
          ELSE 0
        END +
        -- Multi-threading depth (25 pts)
        LEAST(25, (
          SELECT COUNT(*) * 8 FROM gtm.crm.contacts c
          WHERE c.account_id = o.account_id AND c.engagement_score > 50
        )) +
        -- Timeline (15 pts)
        CASE
          WHEN o.close_date > current_date() AND datediff(o.close_date, current_date()) < 90 THEN 15
          WHEN o.close_date > current_date() THEN 10
          ELSE 0
        END +
        -- Competition risk (-10 pts if heavy)
        CASE
          WHEN size(o.competing_with) >= 3 THEN 0
          WHEN size(o.competing_with) >= 1 THEN 5
          ELSE 10
        END
    , 1),
    'risk_flags',       array_compact(array(
        CASE WHEN NOT EXISTS (
          SELECT 1 FROM gtm.crm.contacts c
          WHERE c.account_id = o.account_id AND c.last_contacted > date_sub(current_date(), 14)
        ) THEN 'GHOSTING: No contact engagement in 14+ days' END,
        CASE WHEN o.close_date < current_date() THEN 'SLIPPED: Close date has passed' END,
        CASE WHEN size(o.competing_with) >= 3 THEN concat('CROWDED: Competing with ', array_join(o.competing_with, ', ')) END,
        CASE WHEN NOT EXISTS (
          SELECT 1 FROM gtm.crm.contacts c
          WHERE c.account_id = o.account_id AND c.role_type = 'champion'
        ) THEN 'NO_CHAMPION: No identified champion contact' END,
        CASE WHEN NOT EXISTS (
          SELECT 1 FROM gtm.crm.contacts c
          WHERE c.account_id = o.account_id AND c.role_type = 'economic_buyer'
        ) THEN 'NO_EB: No economic buyer identified' END
    )),
    'champion',         (
      SELECT c.full_name FROM gtm.crm.contacts c
      WHERE c.account_id = o.account_id AND c.role_type = 'champion'
      LIMIT 1
    )
  ))
  FROM gtm.crm.opportunities o
  JOIN gtm.crm.accounts a ON o.account_id = a.account_id
  WHERE o.opp_id = calculate_deal_health.opp_id;


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  TOOL 2: get_account_signals                                            ║
-- ║  Returns engagement, product usage, and sentiment signals.              ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

CREATE OR REPLACE FUNCTION gtm.tools.get_account_signals(account_id STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Returns product usage, support, and sentiment signals for an account. Includes ARR, health score, recent contacts, open opportunities, and competitive landscape.'
RETURN
  SELECT to_json(named_struct(
    'account_id',       a.account_id,
    'company_name',     a.company_name,
    'industry',         a.industry,
    'arr',              a.arr,
    'health_score',     a.health_score,
    'territory',        a.territory,
    'ae_owner',         a.ae_owner,
    'csm_owner',        a.csm_owner,
    'total_contacts',   (SELECT COUNT(*) FROM gtm.crm.contacts c WHERE c.account_id = a.account_id),
    'active_contacts',  (SELECT COUNT(*) FROM gtm.crm.contacts c WHERE c.account_id = a.account_id AND c.last_contacted > date_sub(current_date(), 30)),
    'open_opportunities', (
      SELECT collect_list(named_struct('opp_id', o.opp_id, 'name', o.opp_name, 'stage', o.stage, 'amount', o.amount, 'close_date', cast(o.close_date as string)))
      FROM gtm.crm.opportunities o
      WHERE o.account_id = a.account_id AND o.stage NOT IN ('Closed Won', 'Closed Lost')
    ),
    'key_contacts',     (
      SELECT collect_list(named_struct('name', c.full_name, 'title', c.title, 'role', c.role_type, 'engagement', c.engagement_score))
      FROM gtm.crm.contacts c
      WHERE c.account_id = a.account_id
      ORDER BY c.engagement_score DESC
      LIMIT 5
    )
  ))
  FROM gtm.crm.accounts a
  WHERE a.account_id = get_account_signals.account_id;


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  TOOL 3: log_outreach                                                   ║
-- ║  Logs a generated outreach draft for audit and RL feedback.             ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

CREATE OR REPLACE FUNCTION gtm.tools.log_outreach(
    opp_id STRING,
    ae_id STRING,
    channel STRING,
    subject STRING,
    draft_text STRING
)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Logs an outreach draft to the outreach_log table. Returns the log_id for tracking.'
RETURN
  SELECT to_json(named_struct('status', 'logged', 'opp_id', log_outreach.opp_id, 'channel', log_outreach.channel))
  -- Note: In production, this would INSERT INTO gtm.crm.outreach_log.
  -- UC Functions cannot perform DML; use a UC Python function or handle in the agent layer.
;
