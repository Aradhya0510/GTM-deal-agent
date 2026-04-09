"""
04 · Seed Demo Data — Populate Lakebase CRM tables and Delta source tables.

Run as a Databricks notebook. Requires:
  - Lakebase instance 'gtm-memory' provisioned
  - Schemas from 00_create_catalog_schema.sql created
  - Tables from 01_lakebase_schema.sql created
"""

from datetime import date, datetime, timedelta

from pyspark.sql import SparkSession
import pyspark.sql.functions as F

spark = SparkSession.builder.getOrCreate()

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CRM DATA — Lakebase (via Spark write to UC tables)                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝

# --- Accounts ---
accounts = [
    ("ACC-1001", "Meridian Health Systems", "Healthcare", 3200000.00, 12000, "West", "csm-alex@company.com", "ae-jamie@company.com", 78.5),
    ("ACC-1002", "Apex Financial Group", "Financial Services", 5100000.00, 28000, "East", "csm-priya@company.com", "ae-jamie@company.com", 65.2),
    ("ACC-1003", "NovaTech Solutions", "Technology", 920000.00, 3500, "West", "csm-alex@company.com", "ae-sarah@company.com", 82.1),
    ("ACC-1004", "Pacific Retail Holdings", "Retail", 2400000.00, 18000, "Central", "csm-mike@company.com", "ae-sarah@company.com", 71.8),
    ("ACC-1005", "Summit Manufacturing Co", "Manufacturing", 680000.00, 5200, "East", "csm-priya@company.com", "ae-jamie@company.com", 88.3),
    ("ACC-1006", "Atlas Cloud Services", "Technology", 1500000.00, 8000, "West", "csm-alex@company.com", "ae-jamie@company.com", 55.0),
]

accounts_df = spark.createDataFrame(
    accounts,
    ["account_id", "company_name", "industry", "arr", "employee_count", "territory", "csm_owner", "ae_owner", "health_score"],
)
accounts_df.write.mode("overwrite").saveAsTable("gtm.crm.accounts")

# --- Contacts ---
contacts = [
    # Meridian Health
    ("CON-2001", "ACC-1001", "Sarah Chen", "VP of IT Operations", "sarah.chen@meridianhealth.com", None, "555-0101", "champion", 92.0, datetime(2026, 4, 2)),
    ("CON-2002", "ACC-1001", "Dr. Robert Kim", "CIO", "r.kim@meridianhealth.com", None, "555-0102", "economic_buyer", 45.0, datetime(2026, 3, 15)),
    ("CON-2003", "ACC-1001", "Lisa Patel", "Director of Service Desk", "l.patel@meridianhealth.com", None, "555-0103", "technical_evaluator", 78.0, datetime(2026, 3, 28)),
    # Apex Financial
    ("CON-2004", "ACC-1002", "Michael Torres", "VP Engineering", "m.torres@apexfin.com", None, "555-0201", "champion", 88.0, datetime(2026, 3, 20)),
    ("CON-2005", "ACC-1002", "Jennifer Walsh", "CISO", "j.walsh@apexfin.com", None, "555-0202", "economic_buyer", 35.0, datetime(2026, 2, 10)),
    ("CON-2006", "ACC-1002", "David Park", "Security Architect", "d.park@apexfin.com", None, "555-0203", "technical_evaluator", 72.0, datetime(2026, 3, 25)),
    # NovaTech
    ("CON-2007", "ACC-1003", "Amy Rodriguez", "CTO", "a.rodriguez@novatech.io", None, "555-0301", "champion", 95.0, datetime(2026, 4, 5)),
    ("CON-2008", "ACC-1003", "Chris Lee", "VP Product", "c.lee@novatech.io", None, "555-0302", "economic_buyer", 60.0, datetime(2026, 3, 30)),
    # Pacific Retail
    ("CON-2009", "ACC-1004", "Karen Wright", "SVP Customer Experience", "k.wright@pacificretail.com", None, "555-0401", "champion", 70.0, datetime(2026, 3, 10)),
    ("CON-2010", "ACC-1004", "Tom Harris", "Director IT", "t.harris@pacificretail.com", None, "555-0402", "technical_evaluator", 82.0, datetime(2026, 4, 1)),
    # Summit Manufacturing
    ("CON-2011", "ACC-1005", "Maria Gonzalez", "VP Operations", "m.gonzalez@summitmfg.com", None, "555-0501", "champion", 90.0, datetime(2026, 4, 4)),
    # Atlas Cloud
    ("CON-2012", "ACC-1006", "James Liu", "Head of Platform", "j.liu@atlascloud.io", None, "555-0601", "champion", 40.0, datetime(2026, 2, 1)),
    ("CON-2013", "ACC-1006", "Nina Sharma", "CEO", "n.sharma@atlascloud.io", None, "555-0602", "economic_buyer", 15.0, datetime(2025, 12, 15)),
]

contacts_df = spark.createDataFrame(
    contacts,
    ["contact_id", "account_id", "full_name", "title", "email", "personal_email", "phone", "role_type", "engagement_score", "last_contacted"],
)
contacts_df.write.mode("overwrite").saveAsTable("gtm.crm.contacts")

# --- Opportunities ---
opportunities = [
    ("OPP-3001", "ACC-1001", "Meridian ITSM Platform Expansion", "Negotiation", 1800000.00, date(2026, 5, 15), "Send revised SOW with multi-year pricing", ["ServiceNow", "BMC Helix"], "CON-2001", "West"),
    ("OPP-3002", "ACC-1002", "Apex Security Operations Center", "Proposal", 3200000.00, date(2026, 6, 30), "Technical deep-dive with CISO scheduled May 5", ["Splunk", "Palo Alto", "ServiceNow"], "CON-2004", "East"),
    ("OPP-3003", "ACC-1003", "NovaTech Cloud Migration", "Discovery", 450000.00, date(2026, 8, 1), "Schedule discovery workshop with CTO", None, "CON-2007", "West"),
    ("OPP-3004", "ACC-1004", "Pacific Customer Service Mgmt", "Technical Validation", 1100000.00, date(2026, 5, 30), "POC running — review results May 10", ["Zendesk", "Freshworks"], "CON-2009", "Central"),
    ("OPP-3005", "ACC-1005", "Summit Asset Management", "Closed Won", 340000.00, date(2026, 3, 1), None, ["Jira Service Mgmt"], "CON-2011", "East"),
    ("OPP-3006", "ACC-1006", "Atlas Platform Consolidation", "Discovery", 750000.00, date(2026, 9, 15), "Follow up after champion went quiet", ["Atlassian", "PagerDuty"], "CON-2012", "West"),
]

opps_df = spark.createDataFrame(
    opportunities,
    ["opp_id", "account_id", "opp_name", "stage", "amount", "close_date", "next_step", "competing_with", "champion_id", "territory"],
)
opps_df.write.mode("overwrite").saveAsTable("gtm.crm.opportunities")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  VECTOR SEARCH SOURCE TABLES — Delta tables for semantic retrieval      ║
# ╚══════════════════════════════════════════════════════════════════════════╝

# --- Call Transcripts (Gong-style) ---
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
transcripts_df.write.mode("overwrite").saveAsTable("gtm.enablement.call_transcripts")

# --- Battlecards ---
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
battlecards_df.write.mode("overwrite").saveAsTable("gtm.enablement.battlecards")

# --- Deal Stories ---
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
deal_stories_df.write.mode("overwrite").saveAsTable("gtm.enablement.deal_stories")

print("Demo data seeded successfully.")
print(f"  Accounts:     {accounts_df.count()}")
print(f"  Contacts:     {contacts_df.count()}")
print(f"  Opportunities: {opps_df.count()}")
print(f"  Transcripts:  {transcripts_df.count()}")
print(f"  Battlecards:  {battlecards_df.count()}")
print(f"  Deal stories: {deal_stories_df.count()}")
print("\nNext: Run 02_vector_search_indexes.py to create indexes, then trigger sync.")
