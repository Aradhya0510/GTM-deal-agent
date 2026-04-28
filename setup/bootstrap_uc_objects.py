# Databricks notebook source
# MAGIC %md
# MAGIC # Bootstrap UC objects for the GTM Deal Intelligence agent
# MAGIC
# MAGIC Creates **all** UC objects the agent (`deployment/agent.py`) and apps
# MAGIC (`app/app.py`, `showcase/app.py`) expect — flattened into a single schema
# MAGIC `{UC_CATALOG}.{UC_SCHEMA}` so naming matches `agent.py` exactly.
# MAGIC
# MAGIC Idempotent — safe to re-run.

# COMMAND ----------

dbutils.widgets.text("UC_CATALOG", "")
dbutils.widgets.text("UC_SCHEMA", "")
dbutils.widgets.text("VS_ENDPOINT_NAME", "")
dbutils.widgets.text("EMBEDDING_ENDPOINT", "databricks-gte-large-en")

CATALOG = dbutils.widgets.get("UC_CATALOG")
SCHEMA = dbutils.widgets.get("UC_SCHEMA")
VS_ENDPOINT = dbutils.widgets.get("VS_ENDPOINT_NAME")
EMB = dbutils.widgets.get("EMBEDDING_ENDPOINT")
FQ = f"{CATALOG}.{SCHEMA}"

assert CATALOG and SCHEMA and VS_ENDPOINT, "UC_CATALOG, UC_SCHEMA, VS_ENDPOINT_NAME are required"
print(f"Bootstrapping UC objects in {FQ} (VS endpoint: {VS_ENDPOINT}, embedding: {EMB})")

# COMMAND ----------

# MAGIC %md ## 1. CRM tables (accounts, contacts, opportunities, outreach_log)

# COMMAND ----------

from datetime import date, datetime

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    DateType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

spark = SparkSession.builder.getOrCreate()

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ}")

accounts_rows = [
    ("ACC-1001", "Meridian Health Systems", "Healthcare", 3200000.00, 12000, "West", "csm-alex@company.com", "ae-jamie@company.com", 78.5),
    ("ACC-1002", "Apex Financial Group", "Financial Services", 5100000.00, 28000, "East", "csm-priya@company.com", "ae-jamie@company.com", 65.2),
    ("ACC-1003", "NovaTech Solutions", "Technology", 920000.00, 3500, "West", "csm-alex@company.com", "ae-sarah@company.com", 82.1),
    ("ACC-1004", "Pacific Retail Holdings", "Retail", 2400000.00, 18000, "Central", "csm-mike@company.com", "ae-sarah@company.com", 71.8),
    ("ACC-1005", "Summit Manufacturing Co", "Manufacturing", 680000.00, 5200, "East", "csm-priya@company.com", "ae-jamie@company.com", 88.3),
    ("ACC-1006", "Atlas Cloud Services", "Technology", 1500000.00, 8000, "West", "csm-alex@company.com", "ae-jamie@company.com", 55.0),
]
accounts_schema = StructType([
    StructField("account_id", StringType()),
    StructField("company_name", StringType()),
    StructField("industry", StringType()),
    StructField("arr", DoubleType()),
    StructField("employee_count", LongType()),
    StructField("territory", StringType()),
    StructField("csm_owner", StringType()),
    StructField("ae_owner", StringType()),
    StructField("health_score", DoubleType()),
])
spark.createDataFrame(accounts_rows, accounts_schema).write.mode("overwrite").option(
    "delta.enableChangeDataFeed", "true"
).saveAsTable(f"{FQ}.gtm_accounts")

contacts_rows = [
    ("CON-2001", "ACC-1001", "Sarah Chen", "VP of IT Operations", "sarah.chen@meridianhealth.com", None, "555-0101", "champion", 92.0, datetime(2026, 4, 2)),
    ("CON-2002", "ACC-1001", "Dr. Robert Kim", "CIO", "r.kim@meridianhealth.com", None, "555-0102", "economic_buyer", 45.0, datetime(2026, 3, 15)),
    ("CON-2003", "ACC-1001", "Lisa Patel", "Director of Service Desk", "l.patel@meridianhealth.com", None, "555-0103", "technical_evaluator", 78.0, datetime(2026, 3, 28)),
    ("CON-2004", "ACC-1002", "Michael Torres", "VP Engineering", "m.torres@apexfin.com", None, "555-0201", "champion", 88.0, datetime(2026, 3, 20)),
    ("CON-2005", "ACC-1002", "Jennifer Walsh", "CISO", "j.walsh@apexfin.com", None, "555-0202", "economic_buyer", 35.0, datetime(2026, 2, 10)),
    ("CON-2006", "ACC-1002", "David Park", "Security Architect", "d.park@apexfin.com", None, "555-0203", "technical_evaluator", 72.0, datetime(2026, 3, 25)),
    ("CON-2007", "ACC-1003", "Amy Rodriguez", "CTO", "a.rodriguez@novatech.io", None, "555-0301", "champion", 95.0, datetime(2026, 4, 5)),
    ("CON-2008", "ACC-1003", "Chris Lee", "VP Product", "c.lee@novatech.io", None, "555-0302", "economic_buyer", 60.0, datetime(2026, 3, 30)),
    ("CON-2009", "ACC-1004", "Karen Wright", "SVP Customer Experience", "k.wright@pacificretail.com", None, "555-0401", "champion", 70.0, datetime(2026, 3, 10)),
    ("CON-2010", "ACC-1004", "Tom Harris", "Director IT", "t.harris@pacificretail.com", None, "555-0402", "technical_evaluator", 82.0, datetime(2026, 4, 1)),
    ("CON-2011", "ACC-1005", "Maria Gonzalez", "VP Operations", "m.gonzalez@summitmfg.com", None, "555-0501", "champion", 90.0, datetime(2026, 4, 4)),
    ("CON-2012", "ACC-1006", "James Liu", "Head of Platform", "j.liu@atlascloud.io", None, "555-0601", "champion", 40.0, datetime(2026, 2, 1)),
    ("CON-2013", "ACC-1006", "Nina Sharma", "CEO", "n.sharma@atlascloud.io", None, "555-0602", "economic_buyer", 15.0, datetime(2025, 12, 15)),
]
contacts_schema = StructType([
    StructField("contact_id", StringType()),
    StructField("account_id", StringType()),
    StructField("full_name", StringType()),
    StructField("title", StringType()),
    StructField("email", StringType()),
    StructField("personal_email", StringType()),
    StructField("phone", StringType()),
    StructField("role_type", StringType()),
    StructField("engagement_score", DoubleType()),
    StructField("last_contacted", TimestampType()),
])
spark.createDataFrame(contacts_rows, contacts_schema).write.mode("overwrite").option(
    "delta.enableChangeDataFeed", "true"
).saveAsTable(f"{FQ}.gtm_contacts")

opportunities_rows = [
    ("OPP-3001", "ACC-1001", "Meridian ITSM Platform Expansion", "Negotiation", 1800000.00, date(2026, 5, 15), "Send revised SOW with multi-year pricing", ["ServiceNow", "BMC Helix"], "CON-2001", "West"),
    ("OPP-3002", "ACC-1002", "Apex Security Operations Center", "Proposal", 3200000.00, date(2026, 6, 30), "Technical deep-dive with CISO scheduled May 5", ["Splunk", "Palo Alto", "ServiceNow"], "CON-2004", "East"),
    ("OPP-3003", "ACC-1003", "NovaTech Cloud Migration", "Discovery", 450000.00, date(2026, 8, 1), "Schedule discovery workshop with CTO", [], "CON-2007", "West"),
    ("OPP-3004", "ACC-1004", "Pacific Customer Service Mgmt", "Technical Validation", 1100000.00, date(2026, 5, 30), "POC running — review results May 10", ["Zendesk", "Freshworks"], "CON-2009", "Central"),
    ("OPP-3005", "ACC-1005", "Summit Asset Management", "Closed Won", 340000.00, date(2026, 3, 1), None, ["Jira Service Mgmt"], "CON-2011", "East"),
    ("OPP-3006", "ACC-1006", "Atlas Platform Consolidation", "Discovery", 750000.00, date(2026, 9, 15), "Follow up after champion went quiet", ["Atlassian", "PagerDuty"], "CON-2012", "West"),
]
opportunities_schema = StructType([
    StructField("opp_id", StringType()),
    StructField("account_id", StringType()),
    StructField("opp_name", StringType()),
    StructField("stage", StringType()),
    StructField("amount", DoubleType()),
    StructField("close_date", DateType()),
    StructField("next_step", StringType()),
    StructField("competing_with", ArrayType(StringType())),
    StructField("champion_id", StringType()),
    StructField("territory", StringType()),
])
spark.createDataFrame(opportunities_rows, opportunities_schema).write.mode("overwrite").option(
    "delta.enableChangeDataFeed", "true"
).saveAsTable(f"{FQ}.gtm_opportunities")

# Empty outreach_log table — populated by the agent at runtime
spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {FQ}.gtm_outreach_log (
      log_id STRING,
      opp_id STRING,
      ae_id STRING,
      channel STRING,
      subject STRING,
      draft_text STRING,
      approved BOOLEAN,
      sent_at TIMESTAMP,
      created_at TIMESTAMP
    ) USING DELTA
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
    """
)

print("CRM tables created and seeded.")

# COMMAND ----------

# MAGIC %md ## 2. Vector Search source tables (transcripts, battlecards, deal stories)

# COMMAND ----------

call_transcripts = [
    ("TR-001", "ACC-1001", "OPP-3001", "2026-03-28", "Sarah Chen (Meridian), Jamie Torres (AE)",
     "Sarah expressed strong interest in consolidating from 3 separate ITSM tools to a single platform. Key pain point: incident response times averaging 4 hours across disconnected systems. She mentioned board pressure to reduce IT ops spend by 15% this fiscal year. Sarah confirmed she has budget authority up to $2M but needs CIO sign-off above that. She asked specifically about our ServiceNow integration capabilities and whether we can maintain their existing Slack workflows. Competitive note: they had a BMC demo last week but found the UI 'clunky'. Sarah wants a revised SOW by April 10.",
     "Positive — strong buying signals, budget confirmed, competitive advantage on UX", "positive"),
    ("TR-002", "ACC-1001", "OPP-3001", "2026-03-15", "Dr. Robert Kim (Meridian CIO), Sarah Chen, Jamie Torres (AE)",
     "Dr. Kim joined for the executive briefing. He's focused on total cost of ownership over 3 years, not just license cost. Asked tough questions about implementation timeline — they need to migrate off legacy HP Service Manager by Q3. He mentioned their compliance team requires SOC2 Type II and HIPAA BAA. Kim was lukewarm but not negative — he trusts Sarah's technical judgment. Key quote: 'If Sarah's team says it works, I'll back it, but I need the numbers to make sense.' Follow-up: send TCO comparison vs current stack.",
     "Neutral — CIO needs ROI justification, trusts champion", "neutral"),
    ("TR-003", "ACC-1002", "OPP-3002", "2026-03-25", "David Park (Apex), Michael Torres (Apex), Sarah Lee (SE)",
     "Technical deep-dive on security operations. David is evaluating our SOAR capabilities against Splunk SOAR and Palo Alto XSOAR. His main concern: API integration depth with their existing CrowdStrike and Zscaler stack. Michael (champion) pushed hard on our AI-powered incident triage — this is his pet project. David was impressed by the demo but wants a POC focused on their top 10 alert types. Competitive note: Palo Alto is offering aggressive discounting. Michael said: 'We need to get Jennifer (CISO) excited about the AI angle — that's how we win budget.'",
     "Mixed — strong champion, technical evaluator cautious, competitive pressure on price", "mixed"),
    ("TR-004", "ACC-1002", "OPP-3002", "2026-02-10", "Jennifer Walsh (Apex CISO), Jamie Torres (AE)",
     "Initial intro call with CISO. Jennifer is under board mandate to reduce mean-time-to-respond from 45 min to under 15 min. She manages a team of 12 security analysts who are overwhelmed with alert fatigue — 2000+ alerts/day, 80% false positives. Budget approved for a 'transformational security platform' but she hasn't committed to a vendor. She's skeptical of AI claims: 'Everyone says AI, show me the data.' Wants case studies from financial services companies of similar size. Note: she reports directly to the CEO, unusual for a CISO.",
     "Early stage — high authority, skeptical buyer, needs proof points", "neutral"),
    ("TR-005", "ACC-1003", "OPP-3003", "2026-04-05", "Amy Rodriguez (NovaTech CTO), Sarah Kim (AE)",
     "Discovery call. Amy is leading a company-wide cloud migration from on-prem to multi-cloud (AWS primary, Azure secondary). Their current ticketing system is a custom-built Django app that's falling apart. She wants a platform that can handle both IT and developer workflows in one place. Strong interest in our API-first architecture. No formal evaluation yet — we're the first vendor she's talking to. She wants to move fast: 'If this works, I want to be live by August.' Budget is $500K approved, could stretch to $600K for the right solution.",
     "Positive — early mover advantage, technical buyer, fast timeline", "positive"),
    ("TR-006", "ACC-1004", "OPP-3004", "2026-04-01", "Tom Harris (Pacific Retail), Sarah Kim (AE)",
     "POC mid-point check-in. Tom's team has been running our customer service module for 2 weeks alongside Zendesk. Initial feedback: agents love the AI-suggested responses (30% faster resolution) but the reporting dashboards need work compared to Zendesk Explore. Karen (SVP CX) hasn't seen the POC yet — Tom wants to clean up the dashboards before showing her. Concern: Freshworks came in with a bid 40% lower than ours. Tom's advice: 'Focus on the AI story and the integration with our existing ServiceNow ITSM — that's what Karen cares about.'",
     "Cautiously positive — POC showing value, price pressure from Freshworks", "mixed"),
    ("TR-007", "ACC-1006", "OPP-3006", "2026-02-01", "James Liu (Atlas Cloud), Jamie Torres (AE)",
     "James reached out after seeing our booth at KubeCon. Atlas Cloud runs a multi-tenant SaaS platform and their incident management is split across PagerDuty (alerting), Jira (ticketing), and a homegrown status page. He wants consolidation but his CEO Nina hasn't approved budget. James: 'I believe in this but I need to build a business case. Can you help me with ROI data for platform consolidation?' Note: James is a former ServiceNow employee — he knows the space well and has strong opinions about architecture.",
     "Stalled — interested champion but no budget approval, needs ROI support", "neutral"),
]
transcripts_df = spark.createDataFrame(
    call_transcripts,
    ["transcript_id", "account_id", "opp_id", "call_date", "participants", "transcript_text", "summary", "sentiment"],
)
transcripts_df.write.mode("overwrite").option("delta.enableChangeDataFeed", "true").saveAsTable(f"{FQ}.gtm_call_transcripts")

battlecards = [
    ("BC-001", "ServiceNow", "ITSM",
     "ServiceNow ITSM Battlecard\n\nStrengths to counter:\n- Market leader brand recognition\n- Deep ITSM module maturity (30+ years)\n- Large partner ecosystem\n\nWhere we win:\n- 3x faster implementation (weeks not months)\n- AI-native from day one (not bolted-on)\n- 40% lower TCO over 3 years (Forrester TEI study)\n- Modern API-first architecture vs ServiceNow's legacy platform\n- Real-time analytics vs ServiceNow's batch reporting\n\nKiller question: 'How long did your last ServiceNow upgrade take, and how much customization did you lose?'\n\nProof points:\n- Meridian Health: migrated from ServiceNow in 8 weeks, 60% reduction in incident response time\n- First National Bank: chose us over ServiceNow for 'AI that actually works out of the box'",
     "Speed to value, AI-native, lower TCO, modern architecture",
     "Ask about upgrade pain, customization lock-in, time-to-value on AI features",
     "2026-03-15"),
    ("BC-002", "BMC Helix", "ITSM",
     "BMC Helix Battlecard\n\nStrengths to counter:\n- Strong in large enterprise (10K+ employees)\n- Good multi-cloud discovery/CMDB\n- AIOps capabilities improving\n\nWhere we win:\n- User experience (BMC UI consistently rated lower in G2/Gartner peer reviews)\n- Faster time to value (BMC implementations average 6-9 months)\n- Better developer experience and API quality\n- More intuitive workflow builder\n\nKiller question: 'Have your end users actually adopted BMC, or are they working around it?'\n\nProof points:\n- GlobalTech: switched from BMC citing 'admin overhead 3x what was promised'\n- Healthcare Corp: BMC POC failed on UX; chose us after 2-week trial",
     "UX superiority, faster implementation, developer experience",
     "Focus on end-user adoption rates, admin burden, actual vs promised implementation time",
     "2026-02-28"),
    ("BC-003", "Splunk SOAR / Palo Alto XSOAR", "Security Operations",
     "Splunk SOAR / Palo Alto XSOAR Battlecard\n\nStrengths to counter:\n- Deep security-specific playbook libraries\n- Strong integration with Splunk SIEM / Cortex XDR\n- Large security community\n\nWhere we win:\n- Unified IT + Security operations (one platform, not two silos)\n- AI-powered triage reduces false positives by 80% (vs manual playbooks)\n- Lower total cost — no separate SOAR license on top of SIEM\n- Non-security teams (IT, DevOps) can use the same platform\n\nKiller question: 'How much time does your team spend maintaining SOAR playbooks vs actually responding to incidents?'\n\nProof points:\n- Apex Financial (in pipeline): impressed by AI triage demo, champion pushing for consolidation\n- SecureBank: reduced SOC team alert fatigue by 70% in first quarter",
     "Unified platform, AI triage, lower total cost, cross-team usage",
     "Highlight playbook maintenance burden, silo costs, AI accuracy on real alert data",
     "2026-03-20"),
    ("BC-004", "Zendesk / Freshworks", "Customer Service",
     "Zendesk / Freshworks Battlecard\n\nStrengths to counter:\n- Zendesk: strong brand in mid-market CS, good reporting (Explore)\n- Freshworks: aggressive pricing, fast deployment\n\nWhere we win:\n- AI agent resolution (not just suggestion — actual autonomous resolution of L1 tickets)\n- Seamless ITSM + CS on one platform (critical for companies with internal + external service)\n- Enterprise-grade security and compliance (SOC2, HIPAA, FedRAMP)\n- Workflow automation across IT and customer service boundaries\n\nKiller question: 'What happens when a customer issue requires an internal IT escalation — how many systems does that touch today?'\n\nProof points:\n- Pacific Retail POC: 30% faster resolution with AI-suggested responses\n- RetailMax: consolidated Zendesk + Jira into single platform, saved $200K/year",
     "AI autonomous resolution, unified IT+CS, enterprise compliance",
     "Focus on cross-boundary workflows, total platform cost, AI resolution vs suggestion",
     "2026-03-25"),
]
battlecards_df = spark.createDataFrame(
    battlecards,
    ["card_id", "competitor", "use_case", "content", "win_themes", "objection_handlers", "last_updated"],
)
battlecards_df.write.mode("overwrite").option("delta.enableChangeDataFeed", "true").saveAsTable(f"{FQ}.gtm_battlecards")

deal_stories = [
    ("DS-001", "Healthcare", 2100000.00, "ITSM Platform Consolidation", "Won",
     "Regional hospital network with 15K employees was running HP Service Manager, BMC for asset management, and a custom SharePoint ticketing system. Key moment: CIO saw a live demo where our AI correctly triaged and routed a P1 incident in 8 seconds vs their current 4-hour average. The champion (VP IT Ops) ran an internal benchmark showing 60% reduction in resolution time during the 4-week POC. Closed in 3 months from first meeting. Competitive: beat ServiceNow on implementation speed (8 weeks vs ServiceNow's 6-month estimate).",
     "Live AI demo, internal benchmark data, fast POC results, implementation speed advantage", "ServiceNow"),
    ("DS-002", "Financial Services", 4500000.00, "Security Operations Transformation", "Won",
     "Large bank with 30K employees, SOC team of 20 analysts drowning in 5000+ daily alerts. CISO mandated reduction in MTTR from 1 hour to 15 minutes. Our AI triage reduced actionable alerts by 80%, and the remaining 20% were auto-enriched with threat intel context. Key moment: during the POC, our system caught a real credential stuffing attack 23 minutes before their existing Splunk SOAR detected it. CFO approved expanded budget when CISO presented the 'real incident caught' story at the board. Competitive: beat Palo Alto XSOAR on unified platform vision — bank didn't want two separate platforms for IT and security.",
     "Real incident detection during POC, 80% alert reduction, board-level storytelling", "Palo Alto XSOAR"),
    ("DS-003", "Retail", 1200000.00, "Customer Service Platform", "Lost",
     "Multi-brand retailer with 20K employees evaluated us against Jira Service Management and Zendesk. Our AI features won the technical evaluation but we lost on price — Jira came in at 55% of our cost with a 3-year lock-in. The champion (Director of CX) fought for us but the CFO overruled citing budget constraints after a bad Q4. Lesson: should have engaged the CFO earlier with TCO analysis showing long-term savings. The customer called 9 months later asking to revisit — Jira implementation was 4 months behind schedule.",
     "Lost on price, should have engaged CFO earlier with TCO, competitor implementation delays validated our timeline claims", "Jira Service Management"),
    ("DS-004", "Technology", 800000.00, "DevOps + ITSM Convergence", "Won",
     "SaaS company with 2K engineers wanted to merge their PagerDuty alerting, Jira ticketing, and Statuspage into one platform. CTO was the champion and decision maker. Key differentiator: our API-first architecture and native CI/CD integrations. Won without a formal RFP — CTO did a self-service POC over a weekend and had 10 engineers onboarded by Monday. Competitive: PagerDuty + Atlassian bundle was cheaper but CTO hated context-switching between tools.",
     "Self-service POC, developer experience, API-first resonated with technical buyer", "PagerDuty + Atlassian"),
    ("DS-005", "Manufacturing", 450000.00, "Asset Management + Field Service", "Won",
     "Mid-size manufacturer needed to track 50K+ assets across 12 factories and coordinate field service for 200 technicians. Existing system was spreadsheets and email. Our IoT integration and mobile-first field app were the deciding factors. Champion (VP Ops) said: 'Your field app is the first enterprise software my technicians actually want to use.' Closed in 6 weeks — fastest enterprise deal that quarter. No serious competition — they'd already tried and failed with SAP.",
     "Mobile-first UX, IoT integration, fast close cycle, user adoption story", "SAP"),
]
deal_stories_df = spark.createDataFrame(
    deal_stories,
    ["story_id", "industry", "deal_size", "use_case", "outcome", "narrative", "key_moments", "competitor"],
)
deal_stories_df.write.mode("overwrite").option("delta.enableChangeDataFeed", "true").saveAsTable(f"{FQ}.gtm_deal_stories")

print("VS source tables created and seeded.")

# COMMAND ----------

# MAGIC %md ## 3. Memory inspection tables (Delta mirrors of Lakebase memory)

# COMMAND ----------

# These Delta tables mirror the Lakebase memory tables for the showcase app's
# memory-inspection panels. Lakebase remains the source of truth at runtime.

ae_profiles_rows = [
    ("ae-jamie@company.com", '{"max_words": 120, "tone": "direct and professional", "greeting": "Hi {first_name},"}',
     '{"preferred_cta": "15-minute call this week", "sign_off": "Best, Jamie", "include_proof_points": true}',
     ["ServiceNow"], '{"bullet_points": true, "bold_key_metrics": true}',
     ["email_max_words:120", "email_tone:direct and professional", "preferred_cta:15-minute call this week"]),
    ("ae-sarah@company.com", '{"max_words": 200, "tone": "warm and consultative", "greeting": "Hey {first_name},"}',
     '{"preferred_cta": "discovery workshop", "sign_off": "Cheers, Sarah", "include_proof_points": true}',
     [], '{"bullet_points": false, "bold_key_metrics": false}',
     ["email_max_words:200", "email_tone:warm and consultative", "preferred_cta:discovery workshop"]),
]
ae_schema = StructType([
    StructField("ae_id", StringType()),
    StructField("email_style", StringType()),
    StructField("outreach_prefs", StringType()),
    StructField("avoid_competitors", ArrayType(StringType())),
    StructField("formatting_prefs", StringType()),
    StructField("raw_preferences", ArrayType(StringType())),
])
spark.createDataFrame(ae_profiles_rows, ae_schema).withColumn(
    "updated_at", F.current_timestamp()
).write.mode("overwrite").saveAsTable(f"{FQ}.memory_ae_profiles")

acct_ctx = [
    ("ACC-1001", "champion_change", "Sarah Chen was promoted to VP of IT Operations in March 2026 — she now has direct budget authority up to $2M", "ae-jamie@company.com", 0.95),
    ("ACC-1001", "competitor_mentioned", "BMC Helix had a demo with Meridian in March 2026 but feedback was negative — UI described as 'clunky'", "ae-jamie@company.com", 0.92),
    ("ACC-1001", "budget_freeze", "Board mandate to reduce IT ops spend by 15% this fiscal year", "ae-jamie@company.com", 0.88),
    ("ACC-1002", "technical_requirement", "CISO Jennifer Walsh requires SOC team MTTR under 15 minutes — current average is 45 minutes", "ae-jamie@company.com", 0.90),
    ("ACC-1002", "competitor_mentioned", "Palo Alto XSOAR offering aggressive discounting on the Apex deal", "ae-jamie@company.com", 0.85),
    ("ACC-1002", "sentiment_shift", "Champion Michael Torres is pushing hard for AI-powered triage — his 'pet project' with executive visibility", "ae-jamie@company.com", 0.87),
    ("ACC-1006", "champion_change", "James Liu (Head of Platform) went quiet in Feb 2026 — last known: building internal ROI business case", "ae-jamie@company.com", 0.82),
    ("ACC-1003", "timeline_shift", "CTO Amy Rodriguez wants to be live by August 2026 — fast timeline, no formal RFP yet", "ae-sarah@company.com", 0.91),
]
acct_schema = StructType([
    StructField("account_id", StringType()),
    StructField("context_type", StringType()),
    StructField("content", StringType()),
    StructField("ae_id", StringType()),
    StructField("confidence", DoubleType()),
])
spark.createDataFrame(acct_ctx, acct_schema).withColumn(
    "extracted_at", F.current_timestamp()
).write.mode("overwrite").saveAsTable(f"{FQ}.memory_account_context")

deal_decisions = [
    ("OPP-3001", "ae-jamie@company.com", "Focus the executive briefing on 3-year TCO comparison vs current HP Service Manager + BMC stack", "accepted", "Good call — Kim is all about the numbers"),
    ("OPP-3002", "ae-jamie@company.com", "Lead with AI triage metrics in the email to CISO", "modified", "Good data but Jennifer is skeptical of AI claims — lead with the real incident detection story instead"),
    ("OPP-3006", "ae-jamie@company.com", "Offer a 20% discount to re-engage James Liu at Atlas Cloud", "rejected", "Too early for discounts — James needs help building the internal business case first"),
]
dec_schema = StructType([
    StructField("opp_id", StringType()),
    StructField("ae_id", StringType()),
    StructField("recommendation", StringType()),
    StructField("ae_action", StringType()),
    StructField("ae_feedback", StringType()),
])
spark.createDataFrame(deal_decisions, dec_schema).withColumn(
    "decided_at", F.current_timestamp()
).write.mode("overwrite").saveAsTable(f"{FQ}.memory_deal_decisions")

print("Memory inspection tables created and seeded.")

# COMMAND ----------

# MAGIC %md ## 4. Audit table

# COMMAND ----------

# Schema must match the INSERT in agent.py: event_id, event_type, ae_id, thread_id, detail, created_at
# The agent explicitly passes current_timestamp() in every INSERT, so no DEFAULT is needed.
spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {FQ}.audit_agent_access (
      event_id STRING NOT NULL,
      event_type STRING NOT NULL,
      ae_id STRING,
      thread_id STRING,
      detail STRING,
      created_at TIMESTAMP
    ) USING DELTA
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
    COMMENT 'Audit log for the GTM agent — security events and tool access'
    """
)

print("Audit table created.")

# COMMAND ----------

# MAGIC %md ## 5. UC Functions (calculate_deal_health, get_account_signals)
# MAGIC
# MAGIC Use `RETURNS TABLE(result STRING)` per CLAUDE.md learning — scalar
# MAGIC `RETURNS STRING` treats the body as a correlated subquery when the
# MAGIC parameter is referenced in WHERE.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {FQ}.calculate_deal_health(opp_id STRING)
RETURNS TABLE(result STRING)
COMMENT 'Calculates deal health score (0-100) with risk flags for an opportunity. Returns JSON with score breakdown, stage, days to close, champion, and specific risk flags.'
RETURN
  SELECT to_json(named_struct(
    'opp_id',           o.opp_id,
    'account',          a.company_name,
    'stage',            o.stage,
    'amount',           o.amount,
    'days_to_close',    datediff(o.close_date, current_date()),
    'health_score',     ROUND(
        CASE
          WHEN o.stage = 'Negotiation' THEN 30
          WHEN o.stage = 'Proposal' THEN 22
          WHEN o.stage = 'Technical Validation' THEN 15
          WHEN o.stage = 'Discovery' THEN 8
          ELSE 5
        END +
        CASE
          WHEN EXISTS (
            SELECT 1 FROM {FQ}.gtm_contacts c
            WHERE c.account_id = o.account_id AND c.last_contacted > date_sub(current_date(), 7)
          ) THEN 20
          WHEN EXISTS (
            SELECT 1 FROM {FQ}.gtm_contacts c
            WHERE c.account_id = o.account_id AND c.last_contacted > date_sub(current_date(), 14)
          ) THEN 10
          ELSE 0
        END +
        LEAST(25, (
          SELECT COUNT(*) * 8 FROM {FQ}.gtm_contacts c
          WHERE c.account_id = o.account_id AND c.engagement_score > 50
        )) +
        CASE
          WHEN o.close_date > current_date() AND datediff(o.close_date, current_date()) < 90 THEN 15
          WHEN o.close_date > current_date() THEN 10
          ELSE 0
        END +
        CASE
          WHEN size(o.competing_with) >= 3 THEN 0
          WHEN size(o.competing_with) >= 1 THEN 5
          ELSE 10
        END
    , 1),
    'risk_flags',       array_compact(array(
        CASE WHEN NOT EXISTS (
          SELECT 1 FROM {FQ}.gtm_contacts c
          WHERE c.account_id = o.account_id AND c.last_contacted > date_sub(current_date(), 14)
        ) THEN 'GHOSTING: No contact engagement in 14+ days' END,
        CASE WHEN o.close_date < current_date() THEN 'SLIPPED: Close date has passed' END,
        CASE WHEN size(o.competing_with) >= 3 THEN concat('CROWDED: Competing with ', array_join(o.competing_with, ', ')) END,
        CASE WHEN NOT EXISTS (
          SELECT 1 FROM {FQ}.gtm_contacts c
          WHERE c.account_id = o.account_id AND c.role_type = 'champion'
        ) THEN 'NO_CHAMPION: No identified champion contact' END,
        CASE WHEN NOT EXISTS (
          SELECT 1 FROM {FQ}.gtm_contacts c
          WHERE c.account_id = o.account_id AND c.role_type = 'economic_buyer'
        ) THEN 'NO_EB: No economic buyer identified' END
    )),
    'champion',         (
      SELECT c.full_name FROM {FQ}.gtm_contacts c
      WHERE c.account_id = o.account_id AND c.role_type = 'champion'
      LIMIT 1
    )
  )) AS result
  FROM {FQ}.gtm_opportunities o
  JOIN {FQ}.gtm_accounts a ON o.account_id = a.account_id
  WHERE o.opp_id = calculate_deal_health.opp_id
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {FQ}.get_account_signals(account_id STRING)
RETURNS TABLE(result STRING)
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
    'total_contacts',   (SELECT COUNT(*) FROM {FQ}.gtm_contacts c WHERE c.account_id = a.account_id),
    'active_contacts',  (SELECT COUNT(*) FROM {FQ}.gtm_contacts c WHERE c.account_id = a.account_id AND c.last_contacted > date_sub(current_date(), 30)),
    'open_opportunities', (
      SELECT collect_list(named_struct('opp_id', o.opp_id, 'name', o.opp_name, 'stage', o.stage, 'amount', o.amount, 'close_date', cast(o.close_date as string)))
      FROM {FQ}.gtm_opportunities o
      WHERE o.account_id = a.account_id AND o.stage NOT IN ('Closed Won', 'Closed Lost')
    ),
    'key_contacts',     (
      SELECT collect_list(named_struct('name', c.full_name, 'title', c.title, 'role', c.role_type, 'engagement', c.engagement_score))
      FROM (
        SELECT * FROM {FQ}.gtm_contacts c2
        WHERE c2.account_id = a.account_id
        ORDER BY c2.engagement_score DESC
        LIMIT 5
      ) c
    )
  )) AS result
  FROM {FQ}.gtm_accounts a
  WHERE a.account_id = get_account_signals.account_id
""")

print("UC Functions created.")

# COMMAND ----------

# MAGIC %md ## 6. Vector Search indexes
# MAGIC
# MAGIC Reuses the existing endpoint. Creates 3 delta-sync indexes pointing
# MAGIC at the source tables we just seeded.

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient(disable_notice=True)


def _ensure_index(index_name, source_table, primary_key, embedding_source_column, columns_to_sync):
    full_index_name = f"{FQ}.{index_name}"
    try:
        idx = vsc.get_index(endpoint_name=VS_ENDPOINT, index_name=full_index_name)
        print(f"Index {full_index_name} already exists — triggering sync")
        try:
            idx.sync()
        except Exception as e:
            print(f"  sync skipped: {e}")
        return
    except Exception:
        pass
    vsc.create_delta_sync_index(
        endpoint_name=VS_ENDPOINT,
        index_name=full_index_name,
        source_table_name=f"{FQ}.{source_table}",
        pipeline_type="TRIGGERED",
        primary_key=primary_key,
        embedding_source_column=embedding_source_column,
        embedding_model_endpoint_name=EMB,
        columns_to_sync=columns_to_sync,
    )
    print(f"Created index {full_index_name}")


_ensure_index(
    "gtm_transcripts_idx",
    "gtm_call_transcripts",
    "transcript_id",
    "transcript_text",
    ["transcript_id", "transcript_text", "account_id", "opp_id", "call_date", "participants", "summary", "sentiment"],
)

_ensure_index(
    "gtm_battlecards_idx",
    "gtm_battlecards",
    "card_id",
    "content",
    ["card_id", "content", "competitor", "use_case", "win_themes", "objection_handlers", "last_updated"],
)

_ensure_index(
    "gtm_stories_idx",
    "gtm_deal_stories",
    "story_id",
    "narrative",
    ["story_id", "narrative", "industry", "deal_size", "use_case", "outcome", "key_moments", "competitor"],
)

print("\nVS indexes ready (sync runs in background — first sync takes 30-90s)")

# COMMAND ----------

# MAGIC %md ## Done

# COMMAND ----------

print(f"""
Bootstrap complete.

Schema: {FQ}
  Tables: gtm_accounts, gtm_contacts, gtm_opportunities, gtm_outreach_log,
          gtm_call_transcripts, gtm_battlecards, gtm_deal_stories,
          memory_ae_profiles, memory_account_context, memory_deal_decisions,
          audit_agent_access
  Functions: calculate_deal_health, get_account_signals
  VS indexes (on {VS_ENDPOINT}): gtm_transcripts_idx, gtm_battlecards_idx, gtm_stories_idx

Next:
  1. Wait ~60-90s for VS index initial sync to complete.
  2. ./deploy.sh agent
  3. ./deploy.sh app
  4. ./deploy.sh showcase
""")
