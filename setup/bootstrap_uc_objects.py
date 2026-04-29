# Databricks notebook source
# MAGIC %md
# MAGIC # Bootstrap UC Objects for GTM Deal Intelligence Agent
# MAGIC
# MAGIC Single source of truth for the UC layout the agent expects: catalog,
# MAGIC schema, Delta source tables, demo data, UC functions, and Vector
# MAGIC Search indexes.
# MAGIC
# MAGIC Replaces the older multi-file `setup/0X_*.{sql,py}` scripts which
# MAGIC scattered objects across multiple schemas (`gtm.crm`, `gtm.tools`,
# MAGIC `gtm.vectors`, `gtm.audit`, etc.) that did not match what `agent.py`
# MAGIC actually looks up. The agent reads `UC_CATALOG` / `UC_SCHEMA` from
# MAGIC `os.environ` and constructs flat `{CATALOG}.{SCHEMA}.<name>`
# MAGIC references for every tool, function, index, and table.
# MAGIC
# MAGIC Run via `./deploy.sh bootstrap` (renders widget values from `.env`).

# COMMAND ----------

# ── Configuration via notebook widgets ──
# When run as a job, deployment/deploy_bootstrap.sh populates these from .env.
# When run interactively, set the widget values in the notebook UI.
dbutils.widgets.text("UC_CATALOG", "")
dbutils.widgets.text("UC_SCHEMA", "")
dbutils.widgets.text("VS_ENDPOINT_NAME", "")
dbutils.widgets.text("DATABRICKS_EMBEDDING_ENDPOINT", "databricks-gte-large-en")
dbutils.widgets.dropdown(
    "CREATE_CATALOG", "true", ["true", "false"],
    "Create catalog (set false if catalog already exists with managed location the metastore can't re-validate)",
)

CATALOG = dbutils.widgets.get("UC_CATALOG")
SCHEMA = dbutils.widgets.get("UC_SCHEMA")
VS_ENDPOINT = dbutils.widgets.get("VS_ENDPOINT_NAME")
EMBEDDING_ENDPOINT = dbutils.widgets.get("DATABRICKS_EMBEDDING_ENDPOINT")
CREATE_CATALOG = dbutils.widgets.get("CREATE_CATALOG").lower() == "true"

assert CATALOG and SCHEMA, "UC_CATALOG and UC_SCHEMA widgets must be set"
assert VS_ENDPOINT, "VS_ENDPOINT_NAME widget must be set (use an existing warmed endpoint)"

print(f"Bootstrapping UC objects under {CATALOG}.{SCHEMA}")
print(f"Vector Search endpoint: {VS_ENDPOINT}")
print(f"Embedding endpoint:     {EMBEDDING_ENDPOINT}")
print(f"Create catalog:         {CREATE_CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Catalog and schema

# COMMAND ----------

if CREATE_CATALOG:
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
    print(f"  Catalog {CATALOG} ready")
else:
    print(f"  Skipping catalog creation (CREATE_CATALOG=false)")
    print(f"  Note: assumes {CATALOG} already exists. Use this when the catalog")
    print(f"  has a managed storage root that the metastore can't re-validate")
    print(f"  on a fresh CREATE CATALOG IF NOT EXISTS.")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
print(f"  Schema {CATALOG}.{SCHEMA} ready")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Delta tables (CRM data + audit + VS source)
# MAGIC
# MAGIC VS source tables (`gtm_call_transcripts`, `gtm_battlecards`,
# MAGIC `gtm_deal_stories`) have CDF enabled — required for delta-sync indexes.
# MAGIC
# MAGIC The audit table has NO `DEFAULT current_timestamp()` clause — Delta
# MAGIC column defaults need `delta.feature.allowColumnDefaults` in
# MAGIC TBLPROPERTIES, which we don't enable. The agent's audit-write path
# MAGIC passes `current_timestamp()` explicitly in every INSERT.

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS gtm_accounts (
    account_id      STRING NOT NULL,
    company_name    STRING NOT NULL,
    industry        STRING,
    arr             DOUBLE,
    employee_count  BIGINT,
    territory       STRING,
    csm_owner       STRING,
    ae_owner        STRING,
    health_score    DOUBLE,
    last_updated    TIMESTAMP
) USING DELTA
COMMENT 'GTM account master — company, ARR, territory, ownership'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS gtm_contacts (
    contact_id        STRING NOT NULL,
    account_id        STRING,
    full_name         STRING NOT NULL,
    title             STRING,
    email             STRING,
    personal_email    STRING,
    phone             STRING,
    role_type         STRING,
    engagement_score  DOUBLE,
    last_contacted    TIMESTAMP,
    created_at        TIMESTAMP
) USING DELTA
COMMENT 'GTM contacts — champions, economic buyers, technical evaluators per account'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS gtm_opportunities (
    opp_id          STRING NOT NULL,
    account_id      STRING,
    opp_name        STRING NOT NULL,
    stage           STRING,
    amount          DOUBLE,
    close_date      DATE,
    next_step       STRING,
    competing_with  ARRAY<STRING>,
    champion_id     STRING,
    territory       STRING,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
) USING DELTA
COMMENT 'GTM opportunities — pipeline with stage, amount, competition'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS gtm_outreach_log (
    log_id      STRING NOT NULL,
    opp_id      STRING,
    ae_id       STRING,
    channel     STRING,
    subject     STRING,
    draft_text  STRING,
    approved    BOOLEAN,
    sent_at     TIMESTAMP,
    created_at  TIMESTAMP
) USING DELTA
COMMENT 'Generated outreach drafts (email/LinkedIn/call) for audit + RL feedback'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS audit_agent_access (
    event_id    STRING NOT NULL,
    event_type  STRING NOT NULL,
    ae_id       STRING,
    thread_id   STRING,
    detail      STRING,
    created_at  TIMESTAMP
) USING DELTA
COMMENT 'Audit log for GTM agent — security events and tool access tracking'
""")

# VS source tables — CDF required for delta-sync indexes
spark.sql("""
CREATE TABLE IF NOT EXISTS gtm_call_transcripts (
    transcript_id    STRING NOT NULL,
    account_id       STRING,
    opp_id           STRING,
    call_date        STRING,
    participants     STRING,
    transcript_text  STRING,
    summary          STRING,
    sentiment        STRING
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
COMMENT 'Gong-style call transcripts (VS source for gtm_transcripts_idx)'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS gtm_battlecards (
    card_id             STRING NOT NULL,
    competitor          STRING,
    use_case            STRING,
    content             STRING,
    win_themes          STRING,
    objection_handlers  STRING,
    last_updated        STRING
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
COMMENT 'Competitive battlecards (VS source for gtm_battlecards_idx)'
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS gtm_deal_stories (
    story_id     STRING NOT NULL,
    industry     STRING,
    deal_size    DOUBLE,
    use_case     STRING,
    outcome      STRING,
    narrative    STRING,
    key_moments  STRING,
    competitor   STRING
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
COMMENT 'Won/lost deal stories (VS source for gtm_stories_idx)'
""")

print("  Delta tables created")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Seed demo data
# MAGIC
# MAGIC Idempotent: TRUNCATE then INSERT, so re-running this notebook doesn't
# MAGIC append duplicates.
# MAGIC
# MAGIC Uses raw SQL `INSERT INTO ... VALUES` rather than
# MAGIC `spark.createDataFrame(...)` because per CLAUDE.md learning #14, Row()
# MAGIC with `ARRAY<STRING>` or `datetime` fields fails on serverless with
# MAGIC `CANNOT_DETERMINE_TYPE`.

# COMMAND ----------

spark.sql("TRUNCATE TABLE gtm_accounts")
spark.sql("""
INSERT INTO gtm_accounts VALUES
    ('ACC-1001', 'Meridian Health Systems',  'Healthcare',         3200000.00, 12000, 'West',    'csm-alex@company.com',  'ae-jamie@company.com', 78.5, current_timestamp()),
    ('ACC-1002', 'Apex Financial Group',     'Financial Services', 5100000.00, 28000, 'East',    'csm-priya@company.com', 'ae-jamie@company.com', 65.2, current_timestamp()),
    ('ACC-1003', 'NovaTech Solutions',       'Technology',          920000.00,  3500, 'West',    'csm-alex@company.com',  'ae-sarah@company.com', 82.1, current_timestamp()),
    ('ACC-1004', 'Pacific Retail Holdings',  'Retail',             2400000.00, 18000, 'Central', 'csm-mike@company.com',  'ae-sarah@company.com', 71.8, current_timestamp()),
    ('ACC-1005', 'Summit Manufacturing Co',  'Manufacturing',       680000.00,  5200, 'East',    'csm-priya@company.com', 'ae-jamie@company.com', 88.3, current_timestamp()),
    ('ACC-1006', 'Atlas Cloud Services',     'Technology',         1500000.00,  8000, 'West',    'csm-alex@company.com',  'ae-jamie@company.com', 55.0, current_timestamp())
""")

spark.sql("TRUNCATE TABLE gtm_contacts")
spark.sql("""
INSERT INTO gtm_contacts VALUES
    ('CON-2001', 'ACC-1001', 'Sarah Chen',      'VP of IT Operations',     'sarah.chen@meridianhealth.com', NULL, '555-0101', 'champion',            92.0, TIMESTAMP '2026-04-02 00:00:00', current_timestamp()),
    ('CON-2002', 'ACC-1001', 'Dr. Robert Kim',  'CIO',                     'r.kim@meridianhealth.com',      NULL, '555-0102', 'economic_buyer',      45.0, TIMESTAMP '2026-03-15 00:00:00', current_timestamp()),
    ('CON-2003', 'ACC-1001', 'Lisa Patel',      'Director of Service Desk','l.patel@meridianhealth.com',    NULL, '555-0103', 'technical_evaluator', 78.0, TIMESTAMP '2026-03-28 00:00:00', current_timestamp()),
    ('CON-2004', 'ACC-1002', 'Michael Torres',  'VP Engineering',          'm.torres@apexfin.com',          NULL, '555-0201', 'champion',            88.0, TIMESTAMP '2026-03-20 00:00:00', current_timestamp()),
    ('CON-2005', 'ACC-1002', 'Jennifer Walsh',  'CISO',                    'j.walsh@apexfin.com',           NULL, '555-0202', 'economic_buyer',      35.0, TIMESTAMP '2026-02-10 00:00:00', current_timestamp()),
    ('CON-2006', 'ACC-1002', 'David Park',      'Security Architect',      'd.park@apexfin.com',            NULL, '555-0203', 'technical_evaluator', 72.0, TIMESTAMP '2026-03-25 00:00:00', current_timestamp()),
    ('CON-2007', 'ACC-1003', 'Amy Rodriguez',   'CTO',                     'a.rodriguez@novatech.io',       NULL, '555-0301', 'champion',            95.0, TIMESTAMP '2026-04-05 00:00:00', current_timestamp()),
    ('CON-2008', 'ACC-1003', 'Chris Lee',       'VP Product',              'c.lee@novatech.io',             NULL, '555-0302', 'economic_buyer',      60.0, TIMESTAMP '2026-03-30 00:00:00', current_timestamp()),
    ('CON-2009', 'ACC-1004', 'Karen Wright',    'SVP Customer Experience', 'k.wright@pacificretail.com',    NULL, '555-0401', 'champion',            70.0, TIMESTAMP '2026-03-10 00:00:00', current_timestamp()),
    ('CON-2010', 'ACC-1004', 'Tom Harris',      'Director IT',             't.harris@pacificretail.com',    NULL, '555-0402', 'technical_evaluator', 82.0, TIMESTAMP '2026-04-01 00:00:00', current_timestamp()),
    ('CON-2011', 'ACC-1005', 'Maria Gonzalez',  'VP Operations',           'm.gonzalez@summitmfg.com',      NULL, '555-0501', 'champion',            90.0, TIMESTAMP '2026-04-04 00:00:00', current_timestamp()),
    ('CON-2012', 'ACC-1006', 'James Liu',       'Head of Platform',        'j.liu@atlascloud.io',           NULL, '555-0601', 'champion',            40.0, TIMESTAMP '2026-02-01 00:00:00', current_timestamp()),
    ('CON-2013', 'ACC-1006', 'Nina Sharma',     'CEO',                     'n.sharma@atlascloud.io',        NULL, '555-0602', 'economic_buyer',      15.0, TIMESTAMP '2025-12-15 00:00:00', current_timestamp())
""")

spark.sql("TRUNCATE TABLE gtm_opportunities")
spark.sql("""
INSERT INTO gtm_opportunities VALUES
    ('OPP-3001', 'ACC-1001', 'Meridian ITSM Platform Expansion', 'Negotiation',          1800000.00, DATE '2026-05-15', 'Send revised SOW with multi-year pricing',         array('ServiceNow', 'BMC Helix'),         'CON-2001', 'West',    current_timestamp(), current_timestamp()),
    ('OPP-3002', 'ACC-1002', 'Apex Security Operations Center',  'Proposal',             3200000.00, DATE '2026-06-30', 'Technical deep-dive with CISO scheduled May 5',    array('Splunk', 'Palo Alto', 'ServiceNow'),'CON-2004', 'East',    current_timestamp(), current_timestamp()),
    ('OPP-3003', 'ACC-1003', 'NovaTech Cloud Migration',         'Discovery',             450000.00, DATE '2026-08-01', 'Schedule discovery workshop with CTO',              array(),                                   'CON-2007', 'West',    current_timestamp(), current_timestamp()),
    ('OPP-3004', 'ACC-1004', 'Pacific Customer Service Mgmt',    'Technical Validation', 1100000.00, DATE '2026-05-30', 'POC running — review results May 10',              array('Zendesk', 'Freshworks'),            'CON-2009', 'Central', current_timestamp(), current_timestamp()),
    ('OPP-3005', 'ACC-1005', 'Summit Asset Management',          'Closed Won',            340000.00, DATE '2026-03-01', NULL,                                                array('Jira Service Mgmt'),                'CON-2011', 'East',    current_timestamp(), current_timestamp()),
    ('OPP-3006', 'ACC-1006', 'Atlas Platform Consolidation',     'Discovery',             750000.00, DATE '2026-09-15', 'Follow up after champion went quiet',              array('Atlassian', 'PagerDuty'),           'CON-2012', 'West',    current_timestamp(), current_timestamp())
""")

print("  CRM tables seeded (6 accounts, 13 contacts, 6 opportunities)")

# COMMAND ----------

spark.sql("TRUNCATE TABLE gtm_call_transcripts")
spark.sql("""
INSERT INTO gtm_call_transcripts VALUES
    ('TR-001', 'ACC-1001', 'OPP-3001', '2026-03-28', 'Sarah Chen (Meridian), Jamie Torres (AE)',
     'Sarah expressed strong interest in consolidating from 3 separate ITSM tools to a single platform. Key pain point: incident response times averaging 4 hours across disconnected systems. She mentioned board pressure to reduce IT ops spend by 15% this fiscal year. Sarah confirmed she has budget authority up to $2M but needs CIO sign-off above that. She asked specifically about our ServiceNow integration capabilities and whether we can maintain their existing Slack workflows. Competitive note: they had a BMC demo last week but found the UI clunky. Sarah wants a revised SOW by April 10.',
     'Positive — strong buying signals, budget confirmed, competitive advantage on UX', 'positive'),
    ('TR-002', 'ACC-1001', 'OPP-3001', '2026-03-15', 'Dr. Robert Kim (Meridian CIO), Sarah Chen, Jamie Torres (AE)',
     'Dr. Kim joined for the executive briefing. He is focused on total cost of ownership over 3 years, not just license cost. Asked tough questions about implementation timeline — they need to migrate off legacy HP Service Manager by Q3. He mentioned their compliance team requires SOC2 Type II and HIPAA BAA. Kim was lukewarm but not negative — he trusts Sarah technical judgment. Key quote: If Sarah team says it works, I will back it, but I need the numbers to make sense. Follow-up: send TCO comparison vs current stack.',
     'Neutral — CIO needs ROI justification, trusts champion', 'neutral'),
    ('TR-003', 'ACC-1002', 'OPP-3002', '2026-03-25', 'David Park (Apex), Michael Torres (Apex), Sarah Lee (SE)',
     'Technical deep-dive on security operations. David is evaluating our SOAR capabilities against Splunk SOAR and Palo Alto XSOAR. His main concern: API integration depth with their existing CrowdStrike and Zscaler stack. Michael (champion) pushed hard on our AI-powered incident triage — this is his pet project. David was impressed by the demo but wants a POC focused on their top 10 alert types. Competitive note: Palo Alto is offering aggressive discounting. Michael said: We need to get Jennifer (CISO) excited about the AI angle — that is how we win budget.',
     'Mixed — strong champion, technical evaluator cautious, competitive pressure on price', 'mixed'),
    ('TR-004', 'ACC-1002', 'OPP-3002', '2026-02-10', 'Jennifer Walsh (Apex CISO), Jamie Torres (AE)',
     'Initial intro call with CISO. Jennifer is under board mandate to reduce mean-time-to-respond from 45 min to under 15 min. She manages a team of 12 security analysts who are overwhelmed with alert fatigue — 2000+ alerts/day, 80% false positives. Budget approved for a transformational security platform but she has not committed to a vendor. She is skeptical of AI claims: Everyone says AI, show me the data. Wants case studies from financial services companies of similar size. Note: she reports directly to the CEO, unusual for a CISO.',
     'Early stage — high authority, skeptical buyer, needs proof points', 'neutral'),
    ('TR-005', 'ACC-1003', 'OPP-3003', '2026-04-05', 'Amy Rodriguez (NovaTech CTO), Sarah Kim (AE)',
     'Discovery call. Amy is leading a company-wide cloud migration from on-prem to multi-cloud (AWS primary, Azure secondary). Their current ticketing system is a custom-built Django app that is falling apart. She wants a platform that can handle both IT and developer workflows in one place. Strong interest in our API-first architecture. No formal evaluation yet — we are the first vendor she is talking to. She wants to move fast: If this works, I want to be live by August. Budget is $500K approved, could stretch to $600K for the right solution.',
     'Positive — early mover advantage, technical buyer, fast timeline', 'positive'),
    ('TR-006', 'ACC-1004', 'OPP-3004', '2026-04-01', 'Tom Harris (Pacific Retail), Sarah Kim (AE)',
     'POC mid-point check-in. Tom team has been running our customer service module for 2 weeks alongside Zendesk. Initial feedback: agents love the AI-suggested responses (30% faster resolution) but the reporting dashboards need work compared to Zendesk Explore. Karen (SVP CX) has not seen the POC yet — Tom wants to clean up the dashboards before showing her. Concern: Freshworks came in with a bid 40% lower than ours. Tom advice: Focus on the AI story and the integration with our existing ServiceNow ITSM — that is what Karen cares about.',
     'Cautiously positive — POC showing value, price pressure from Freshworks', 'mixed'),
    ('TR-007', 'ACC-1006', 'OPP-3006', '2026-02-01', 'James Liu (Atlas Cloud), Jamie Torres (AE)',
     'James reached out after seeing our booth at KubeCon. Atlas Cloud runs a multi-tenant SaaS platform and their incident management is split across PagerDuty (alerting), Jira (ticketing), and a homegrown status page. He wants consolidation but his CEO Nina has not approved budget. James: I believe in this but I need to build a business case. Can you help me with ROI data for platform consolidation? Note: James is a former ServiceNow employee — he knows the space well and has strong opinions about architecture.',
     'Stalled — interested champion but no budget approval, needs ROI support', 'neutral')
""")

spark.sql("TRUNCATE TABLE gtm_battlecards")
spark.sql("""
INSERT INTO gtm_battlecards VALUES
    ('BC-001', 'ServiceNow', 'ITSM',
     'ServiceNow ITSM Battlecard. Strengths to counter: market leader brand recognition, deep ITSM module maturity (30+ years), large partner ecosystem. Where we win: 3x faster implementation (weeks not months), AI-native from day one (not bolted-on), 40% lower TCO over 3 years (Forrester TEI study), modern API-first architecture vs legacy, real-time analytics vs batch reporting. Killer question: How long did your last ServiceNow upgrade take, and how much customization did you lose? Proof points: Meridian Health migrated in 8 weeks with 60% reduction in incident response time; First National Bank chose us over ServiceNow for AI that actually works out of the box.',
     'Speed to value, AI-native, lower TCO, modern architecture',
     'Ask about upgrade pain, customization lock-in, time-to-value on AI features',
     '2026-03-15'),
    ('BC-002', 'BMC Helix', 'ITSM',
     'BMC Helix Battlecard. Strengths to counter: strong in large enterprise (10K+ employees), good multi-cloud discovery/CMDB, AIOps capabilities improving. Where we win: user experience (BMC UI consistently rated lower in G2/Gartner peer reviews), faster time to value (BMC implementations average 6-9 months), better developer experience and API quality, more intuitive workflow builder. Killer question: Have your end users actually adopted BMC, or are they working around it? Proof points: GlobalTech switched from BMC citing admin overhead 3x what was promised; Healthcare Corp BMC POC failed on UX and chose us after 2-week trial.',
     'UX superiority, faster implementation, developer experience',
     'Focus on end-user adoption rates, admin burden, actual vs promised implementation time',
     '2026-02-28'),
    ('BC-003', 'Splunk SOAR / Palo Alto XSOAR', 'Security Operations',
     'Splunk SOAR / Palo Alto XSOAR Battlecard. Strengths to counter: deep security-specific playbook libraries, strong integration with Splunk SIEM / Cortex XDR, large security community. Where we win: unified IT + Security operations (one platform, not two silos), AI-powered triage reduces false positives by 80% vs manual playbooks, lower total cost (no separate SOAR license on top of SIEM), non-security teams (IT, DevOps) can use the same platform. Killer question: How much time does your team spend maintaining SOAR playbooks vs actually responding to incidents? Proof points: Apex Financial (in pipeline) impressed by AI triage demo, champion pushing for consolidation; SecureBank reduced SOC team alert fatigue by 70% in first quarter.',
     'Unified platform, AI triage, lower total cost, cross-team usage',
     'Highlight playbook maintenance burden, silo costs, AI accuracy on real alert data',
     '2026-03-20'),
    ('BC-004', 'Zendesk / Freshworks', 'Customer Service',
     'Zendesk / Freshworks Battlecard. Strengths to counter: Zendesk strong brand in mid-market CS with good reporting (Explore); Freshworks aggressive pricing and fast deployment. Where we win: AI agent resolution (not just suggestion — actual autonomous resolution of L1 tickets), seamless ITSM + CS on one platform (critical for companies with internal + external service), enterprise-grade security and compliance (SOC2, HIPAA, FedRAMP), workflow automation across IT and customer service boundaries. Killer question: What happens when a customer issue requires an internal IT escalation — how many systems does that touch today? Proof points: Pacific Retail POC 30% faster resolution with AI-suggested responses; RetailMax consolidated Zendesk + Jira into single platform, saved $200K/year.',
     'AI autonomous resolution, unified IT+CS, enterprise compliance',
     'Focus on cross-boundary workflows, total platform cost, AI resolution vs suggestion',
     '2026-03-25')
""")

spark.sql("TRUNCATE TABLE gtm_deal_stories")
spark.sql("""
INSERT INTO gtm_deal_stories VALUES
    ('DS-001', 'Healthcare',         2100000.00, 'ITSM Platform Consolidation',     'Won',
     'Regional hospital network with 15K employees was running HP Service Manager, BMC for asset management, and a custom SharePoint ticketing system. Key moment: CIO saw a live demo where our AI correctly triaged and routed a P1 incident in 8 seconds vs their current 4-hour average. The champion (VP IT Ops) ran an internal benchmark showing 60% reduction in resolution time during the 4-week POC. Closed in 3 months from first meeting. Competitive: beat ServiceNow on implementation speed (8 weeks vs 6-month estimate).',
     'Live AI demo, internal benchmark data, fast POC results, implementation speed advantage', 'ServiceNow'),
    ('DS-002', 'Financial Services', 4500000.00, 'Security Operations Transformation','Won',
     'Large bank with 30K employees, SOC team of 20 analysts drowning in 5000+ daily alerts. CISO mandated reduction in MTTR from 1 hour to 15 minutes. Our AI triage reduced actionable alerts by 80%, and the remaining 20% were auto-enriched with threat intel context. Key moment: during the POC, our system caught a real credential stuffing attack 23 minutes before their existing Splunk SOAR detected it. CFO approved expanded budget when CISO presented the real incident caught story at the board. Competitive: beat Palo Alto XSOAR on unified platform vision.',
     'Real incident detection during POC, 80% alert reduction, board-level storytelling', 'Palo Alto XSOAR'),
    ('DS-003', 'Retail',              1200000.00, 'Customer Service Platform',       'Lost',
     'Multi-brand retailer with 20K employees evaluated us against Jira Service Management and Zendesk. Our AI features won the technical evaluation but we lost on price — Jira came in at 55% of our cost with a 3-year lock-in. The champion (Director of CX) fought for us but the CFO overruled citing budget constraints after a bad Q4. Lesson: should have engaged the CFO earlier with TCO analysis showing long-term savings. The customer called 9 months later asking to revisit — Jira implementation was 4 months behind schedule.',
     'Lost on price, should have engaged CFO earlier with TCO, competitor implementation delays validated our timeline claims', 'Jira Service Management'),
    ('DS-004', 'Technology',           800000.00, 'DevOps + ITSM Convergence',       'Won',
     'SaaS company with 2K engineers wanted to merge their PagerDuty alerting, Jira ticketing, and Statuspage into one platform. CTO was the champion and decision maker. Key differentiator: our API-first architecture and native CI/CD integrations. Won without a formal RFP — CTO did a self-service POC over a weekend and had 10 engineers onboarded by Monday. Competitive: PagerDuty + Atlassian bundle was cheaper but CTO hated context-switching between tools.',
     'Self-service POC, developer experience, API-first resonated with technical buyer', 'PagerDuty + Atlassian'),
    ('DS-005', 'Manufacturing',        450000.00, 'Asset Management + Field Service','Won',
     'Mid-size manufacturer needed to track 50K+ assets across 12 factories and coordinate field service for 200 technicians. Existing system was spreadsheets and email. Our IoT integration and mobile-first field app were the deciding factors. Champion (VP Ops) said: Your field app is the first enterprise software my technicians actually want to use. Closed in 6 weeks — fastest enterprise deal that quarter. No serious competition — they had already tried and failed with SAP.',
     'Mobile-first UX, IoT integration, fast close cycle, user adoption story', 'SAP')
""")

print("  VS source tables seeded (7 transcripts, 4 battlecards, 5 deal stories)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. UC Functions
# MAGIC
# MAGIC Use `RETURNS TABLE(result STRING)` rather than scalar `RETURNS STRING`
# MAGIC per CLAUDE.md learning #2: scalar UC functions with correlated
# MAGIC subqueries can fail with `MUST_AGGREGATE_CORRELATED_SCALAR_SUBQUERY`.
# MAGIC `UCFunctionToolkit` reads either shape transparently.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION calculate_deal_health(opp_id STRING)
RETURNS TABLE(result STRING)
COMMENT 'Calculates deal health score (0-100) with risk flags for an opportunity. Returns JSON with score breakdown, stage, days to close, champion, and specific risk flags.'
RETURN
  SELECT to_json(named_struct(
    'opp_id',         o.opp_id,
    'account',        a.company_name,
    'stage',          o.stage,
    'amount',         o.amount,
    'days_to_close',  datediff(o.close_date, current_date()),
    'health_score',   ROUND(
        CASE
          WHEN o.stage = 'Negotiation'          THEN 30
          WHEN o.stage = 'Proposal'             THEN 22
          WHEN o.stage = 'Technical Validation' THEN 15
          WHEN o.stage = 'Discovery'            THEN 8
          ELSE 5
        END +
        CASE
          WHEN EXISTS (SELECT 1 FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                       WHERE c.account_id = o.account_id
                         AND c.last_contacted > date_sub(current_date(), 7))   THEN 20
          WHEN EXISTS (SELECT 1 FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                       WHERE c.account_id = o.account_id
                         AND c.last_contacted > date_sub(current_date(), 14))  THEN 10
          ELSE 0
        END +
        LEAST(25, (SELECT COUNT(*) * 8 FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                   WHERE c.account_id = o.account_id AND c.engagement_score > 50)) +
        CASE
          WHEN o.close_date > current_date()
               AND datediff(o.close_date, current_date()) < 90 THEN 15
          WHEN o.close_date > current_date()                   THEN 10
          ELSE 0
        END +
        CASE
          WHEN size(o.competing_with) >= 3 THEN 0
          WHEN size(o.competing_with) >= 1 THEN 5
          ELSE 10
        END
    , 1),
    'risk_flags',     array_compact(array(
        CASE WHEN NOT EXISTS (SELECT 1 FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                              WHERE c.account_id = o.account_id
                                AND c.last_contacted > date_sub(current_date(), 14))
             THEN 'GHOSTING: No contact engagement in 14+ days' END,
        CASE WHEN o.close_date < current_date() THEN 'SLIPPED: Close date has passed' END,
        CASE WHEN size(o.competing_with) >= 3
             THEN concat('CROWDED: Competing with ', array_join(o.competing_with, ', ')) END,
        CASE WHEN NOT EXISTS (SELECT 1 FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                              WHERE c.account_id = o.account_id AND c.role_type = 'champion')
             THEN 'NO_CHAMPION: No identified champion contact' END,
        CASE WHEN NOT EXISTS (SELECT 1 FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                              WHERE c.account_id = o.account_id AND c.role_type = 'economic_buyer')
             THEN 'NO_EB: No economic buyer identified' END
    )),
    'champion',       (SELECT c.full_name FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                       WHERE c.account_id = o.account_id AND c.role_type = 'champion' LIMIT 1)
  )) AS result
  FROM {CATALOG}.{SCHEMA}.gtm_opportunities o
  JOIN {CATALOG}.{SCHEMA}.gtm_accounts a ON o.account_id = a.account_id
  WHERE o.opp_id = calculate_deal_health.opp_id
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION get_account_signals(account_id STRING)
RETURNS TABLE(result STRING)
COMMENT 'Returns ARR, health, contacts, and open opportunities for an account.'
RETURN
  SELECT to_json(named_struct(
    'account_id',         a.account_id,
    'company_name',       a.company_name,
    'industry',           a.industry,
    'arr',                a.arr,
    'health_score',       a.health_score,
    'territory',          a.territory,
    'ae_owner',           a.ae_owner,
    'csm_owner',          a.csm_owner,
    'total_contacts',     (SELECT COUNT(*) FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                            WHERE c.account_id = a.account_id),
    'active_contacts',    (SELECT COUNT(*) FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                            WHERE c.account_id = a.account_id
                              AND c.last_contacted > date_sub(current_date(), 30)),
    'open_opportunities', (SELECT collect_list(named_struct(
                              'opp_id',     o.opp_id,
                              'name',       o.opp_name,
                              'stage',      o.stage,
                              'amount',     o.amount,
                              'close_date', cast(o.close_date as string)))
                            FROM {CATALOG}.{SCHEMA}.gtm_opportunities o
                            WHERE o.account_id = a.account_id
                              AND o.stage NOT IN ('Closed Won', 'Closed Lost')),
    'key_contacts',       (SELECT collect_list(named_struct(
                              'name',       c.full_name,
                              'title',      c.title,
                              'role',       c.role_type,
                              'engagement', c.engagement_score))
                            FROM {CATALOG}.{SCHEMA}.gtm_contacts c
                            WHERE c.account_id = a.account_id
                            ORDER BY c.engagement_score DESC LIMIT 5)
  )) AS result
  FROM {CATALOG}.{SCHEMA}.gtm_accounts a
  WHERE a.account_id = get_account_signals.account_id
""")

print("  UC functions created (calculate_deal_health, get_account_signals)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Vector Search indexes
# MAGIC
# MAGIC Names match exactly what `agent.py` expects:
# MAGIC `gtm_transcripts_idx`, `gtm_battlecards_idx`, `gtm_stories_idx`.
# MAGIC
# MAGIC Uses an EXISTING (already-warmed) VS endpoint — creating new endpoints
# MAGIC takes 20-30+ minutes per CLAUDE.md learning #4. The bootstrap fails
# MAGIC fast with a clear message if the endpoint doesn't exist.

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient
vsc = VectorSearchClient()

try:
    vsc.get_endpoint(VS_ENDPOINT)
    print(f"  Endpoint {VS_ENDPOINT} confirmed")
except Exception as e:
    raise RuntimeError(
        f"VS endpoint '{VS_ENDPOINT}' not found in this workspace. Either create it "
        f"manually first (takes 20-30 min to warm) or set VS_ENDPOINT_NAME in .env "
        f"to an existing endpoint. Original error: {e}"
    )


def _create_or_skip(index_name, source_table, primary_key, source_col):
    full_index = f"{CATALOG}.{SCHEMA}.{index_name}"
    full_source = f"{CATALOG}.{SCHEMA}.{source_table}"
    try:
        vsc.get_index(VS_ENDPOINT, full_index)
        print(f"  Index {full_index} already exists — skipping")
    except Exception:
        vsc.create_delta_sync_index(
            endpoint_name=VS_ENDPOINT,
            index_name=full_index,
            source_table_name=full_source,
            pipeline_type="TRIGGERED",
            primary_key=primary_key,
            embedding_source_column=source_col,
            embedding_model_endpoint_name=EMBEDDING_ENDPOINT,
        )
        print(f"  Created {full_index}")


_create_or_skip("gtm_transcripts_idx", "gtm_call_transcripts", "transcript_id", "transcript_text")
_create_or_skip("gtm_battlecards_idx", "gtm_battlecards",      "card_id",       "content")
_create_or_skip("gtm_stories_idx",     "gtm_deal_stories",     "story_id",     "narrative")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Done

# COMMAND ----------

print("\n  Bootstrap complete.")
print(f"  Tables:    {CATALOG}.{SCHEMA}.{{gtm_accounts, gtm_contacts, gtm_opportunities, gtm_outreach_log, gtm_call_transcripts, gtm_battlecards, gtm_deal_stories, audit_agent_access}}")
print(f"  Functions: {CATALOG}.{SCHEMA}.{{calculate_deal_health, get_account_signals}}")
print(f"  Indexes:   {CATALOG}.{SCHEMA}.{{gtm_transcripts_idx, gtm_battlecards_idx, gtm_stories_idx}}")
print(f"\n  Note: VS index sync runs asynchronously after creation. Check status in the")
print(f"  Vector Search UI — you'll see 'Online' once the embedding pass completes.")

dbutils.notebook.exit(f"Bootstrap complete in {CATALOG}.{SCHEMA}")
