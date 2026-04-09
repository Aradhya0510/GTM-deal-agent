# Databricks notebook source
# MAGIC %md
# MAGIC # Memory Tables Setup — Delta Tables + Seed Data
# MAGIC
# MAGIC Creates long-term memory tables as Delta tables in Unity Catalog and seeds
# MAGIC demo data for the GTM Deal Intelligence Agent.

# COMMAND ----------

CATALOG = "users"
SCHEMA = "aradhya_chouhan"

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create Memory Tables

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS memory_ae_profiles (
    ae_id               STRING NOT NULL,
    email_style         STRING,
    outreach_prefs      STRING,
    avoid_competitors   ARRAY<STRING>,
    formatting_prefs    STRING,
    raw_preferences     ARRAY<STRING>,
    updated_at          TIMESTAMP
)
USING DELTA
COMMENT 'AE preference profiles for long-term memory'
""")
print("Created: memory_ae_profiles")

spark.sql("""
CREATE TABLE IF NOT EXISTS memory_account_context (
    account_id          STRING NOT NULL,
    context_type        STRING NOT NULL,
    content             STRING,
    source_thread_id    STRING,
    ae_id               STRING,
    confidence          DOUBLE,
    extracted_at        TIMESTAMP,
    expires_at          TIMESTAMP
)
USING DELTA
COMMENT 'Account-level cross-session context'
""")
print("Created: memory_account_context")

spark.sql("""
CREATE TABLE IF NOT EXISTS memory_deal_decisions (
    decision_id         STRING NOT NULL,
    opp_id              STRING,
    ae_id               STRING,
    session_thread_id   STRING,
    recommendation      STRING,
    ae_action           STRING,
    ae_feedback         STRING,
    outcome             STRING,
    decided_at          TIMESTAMP
)
USING DELTA
COMMENT 'Deal decision log — agent recommendations vs AE actions'
""")
print("Created: memory_deal_decisions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Seed AE Profiles

# COMMAND ----------

# Clear existing seed data
spark.sql("DELETE FROM memory_ae_profiles WHERE ae_id IN ('ae-jamie@company.com', 'ae-sarah@company.com')")

# Jamie Torres: experienced AE, prefers concise emails, direct tone
spark.sql("""
INSERT INTO memory_ae_profiles VALUES (
    'ae-jamie@company.com',
    '{"max_words": 120, "tone": "direct and professional", "greeting": "Hi {first_name},"}',
    '{"preferred_cta": "15-minute call this week", "sign_off": "Best, Jamie", "include_proof_points": true}',
    array('ServiceNow'),
    '{"bullet_points": true, "bold_key_metrics": true}',
    array('email_max_words:120', 'email_tone:direct and professional', 'avoid_competitor_mention:ServiceNow', 'preferred_cta:15-minute call this week', 'formatting:use bullet points for key metrics'),
    current_timestamp()
)
""")

# Sarah Kim: newer AE, likes detailed analysis, warmer tone
spark.sql("""
INSERT INTO memory_ae_profiles VALUES (
    'ae-sarah@company.com',
    '{"max_words": 200, "tone": "warm and consultative", "greeting": "Hey {first_name},"}',
    '{"preferred_cta": "discovery workshop", "sign_off": "Cheers, Sarah", "include_proof_points": true}',
    array(),
    '{"bullet_points": false, "bold_key_metrics": false}',
    array('email_max_words:200', 'email_tone:warm and consultative', 'preferred_cta:discovery workshop'),
    current_timestamp()
)
""")

print("Seeded: 2 AE profiles (Jamie Torres, Sarah Kim)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Seed Account Context

# COMMAND ----------

# Clear existing seed data
spark.sql("DELETE FROM memory_account_context WHERE source_thread_id = 'seed-data'")

context_inserts = [
    ("ACC-1001", "champion_change", "Sarah Chen was promoted to VP of IT Operations in March 2026 — she now has direct budget authority up to $2M", "ae-jamie@company.com", 0.95),
    ("ACC-1001", "competitor_mentioned", "BMC Helix had a demo with Meridian in March 2026 but feedback was negative — UI described as clunky", "ae-jamie@company.com", 0.92),
    ("ACC-1001", "budget_freeze", "Board mandate to reduce IT ops spend by 15% this fiscal year — champion sees platform consolidation as the path", "ae-jamie@company.com", 0.88),
    ("ACC-1002", "technical_requirement", "CISO Jennifer Walsh requires SOC team MTTR under 15 minutes — current average is 45 minutes", "ae-jamie@company.com", 0.90),
    ("ACC-1002", "competitor_mentioned", "Palo Alto XSOAR offering aggressive discounting on the Apex deal", "ae-jamie@company.com", 0.85),
    ("ACC-1002", "sentiment_shift", "Champion Michael Torres is pushing hard for AI-powered triage — his pet project with executive visibility", "ae-jamie@company.com", 0.87),
    ("ACC-1006", "champion_change", "James Liu (Head of Platform) went quiet in Feb 2026 — last known: building internal ROI business case, no budget approval from CEO", "ae-jamie@company.com", 0.82),
    ("ACC-1003", "timeline_shift", "CTO Amy Rodriguez wants to be live by August 2026 — fast timeline, no formal RFP yet", "ae-sarah@company.com", 0.91),
]

for acct_id, ctx_type, content, ae_id, confidence in context_inserts:
    safe_content = content.replace("'", "\\'")
    spark.sql(f"""
        INSERT INTO memory_account_context VALUES (
            '{acct_id}', '{ctx_type}', '{safe_content}', 'seed-data',
            '{ae_id}', {confidence}, current_timestamp(), NULL
        )
    """)

print(f"Seeded: {len(context_inserts)} account context facts")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Seed Deal Decisions

# COMMAND ----------

import uuid

# Clear existing seed data
spark.sql("DELETE FROM memory_deal_decisions WHERE session_thread_id = 'seed-data'")

decisions = [
    ("OPP-3001", "ae-jamie@company.com", "Focus the executive briefing on 3-year TCO comparison vs current HP Service Manager + BMC stack", "accepted", "Good call — Kim is all about the numbers"),
    ("OPP-3002", "ae-jamie@company.com", "Lead with AI triage metrics in the email to CISO", "modified", "Good data but Jennifer is skeptical of AI claims — lead with the real incident detection story instead"),
    ("OPP-3006", "ae-jamie@company.com", "Offer a 20% discount to re-engage James Liu at Atlas Cloud", "rejected", "Too early for discounts — James needs help building the internal business case first, not a lower price"),
]

for opp_id, ae_id, recommendation, ae_action, feedback in decisions:
    dec_id = str(uuid.uuid4())
    safe_rec = recommendation.replace("'", "\\'")
    safe_fb = feedback.replace("'", "\\'")
    spark.sql(f"""
        INSERT INTO memory_deal_decisions VALUES (
            '{dec_id}', '{opp_id}', '{ae_id}', 'seed-data',
            '{safe_rec}', '{ae_action}', '{safe_fb}', NULL, current_timestamp()
        )
    """)

print(f"Seeded: {len(decisions)} deal decisions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Verify

# COMMAND ----------

ae_count = spark.sql("SELECT COUNT(*) AS c FROM memory_ae_profiles").collect()[0]["c"]
ctx_count = spark.sql("SELECT COUNT(*) AS c FROM memory_account_context").collect()[0]["c"]
dec_count = spark.sql("SELECT COUNT(*) AS c FROM memory_deal_decisions").collect()[0]["c"]

print("=" * 50)
print("Memory Tables Setup Complete")
print("=" * 50)
print(f"  AE Profiles:      {ae_count}")
print(f"  Account Context:  {ctx_count}")
print(f"  Deal Decisions:   {dec_count}")

# Show Jamie's profile
print("\nJamie Torres profile:")
display(spark.sql("SELECT ae_id, email_style, avoid_competitors, raw_preferences FROM memory_ae_profiles WHERE ae_id = 'ae-jamie@company.com'"))
