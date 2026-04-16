# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase Memory Setup — Seed Data into Lakebase Postgres
# MAGIC
# MAGIC Seeds demo data into a Lakebase Postgres instance
# MAGIC using `DatabricksStore` from `databricks-langchain[memory]`.
# MAGIC
# MAGIC Run this as a serverless notebook job after the Lakebase instance is created.

# COMMAND ----------

LAKEBASE_INSTANCE_NAME = ""  # TODO: set your Lakebase instance name
EMBEDDING_ENDPOINT = "databricks-gte-large-en"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Initialize Lakebase DatabricksStore

# COMMAND ----------

from databricks_langchain import DatabricksStore

store = DatabricksStore(
    instance_name=LAKEBASE_INSTANCE_NAME,
    embedding_endpoint=EMBEDDING_ENDPOINT,
    embedding_dims=1024,
)
store.setup()
print(f"Connected to Lakebase instance: {LAKEBASE_INSTANCE_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Initialize CheckpointSaver tables

# COMMAND ----------

from databricks_langchain import CheckpointSaver

checkpointer = CheckpointSaver(instance_name=LAKEBASE_INSTANCE_NAME)
checkpointer.setup()
print("CheckpointSaver tables initialized")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Seed AE Profiles (preferences)

# COMMAND ----------

jamie_prefs = [
    ("email_style", {
        "type": "ae_preference",
        "preference_type": "email_style",
        "preference_value": "direct and professional",
        "content": "email_style:direct and professional, max 120 words, greeting Hi {first_name}",
        "confidence": 0.95,
        "ae_id": "ae-jamie",
    }),
    ("email_max_words", {
        "type": "ae_preference",
        "preference_type": "email_max_words",
        "preference_value": "120",
        "content": "email_max_words:120",
        "confidence": 0.95,
        "ae_id": "ae-jamie",
    }),
    ("preferred_cta", {
        "type": "ae_preference",
        "preference_type": "preferred_cta",
        "preference_value": "15-minute call this week",
        "content": "preferred_cta:15-minute call this week",
        "confidence": 0.90,
        "ae_id": "ae-jamie",
    }),
    ("sign_off", {
        "type": "ae_preference",
        "preference_type": "sign_off",
        "preference_value": "Best, Jamie",
        "content": "sign_off:Best, Jamie",
        "confidence": 0.95,
        "ae_id": "ae-jamie",
    }),
    ("avoid_competitor", {
        "type": "ae_preference",
        "preference_type": "avoid_competitor_mention",
        "preference_value": "ServiceNow",
        "content": "avoid_competitor_mention:ServiceNow",
        "confidence": 0.90,
        "ae_id": "ae-jamie",
    }),
    ("formatting", {
        "type": "ae_preference",
        "preference_type": "formatting",
        "preference_value": "use bullet points for key metrics",
        "content": "formatting:use bullet points for key metrics, bold key numbers",
        "confidence": 0.85,
        "ae_id": "ae-jamie",
    }),
    ("include_proof_points", {
        "type": "ae_preference",
        "preference_type": "include_proof_points",
        "preference_value": "true",
        "content": "include_proof_points:always include a relevant customer proof point",
        "confidence": 0.88,
        "ae_id": "ae-jamie",
    }),
]

for key, value in jamie_prefs:
    store.put(("ae_memories", "ae-jamie"), key, value)
print(f"Seeded {len(jamie_prefs)} preferences for ae-jamie")

sarah_prefs = [
    ("email_style", {
        "type": "ae_preference",
        "preference_type": "email_style",
        "preference_value": "warm and consultative",
        "content": "email_style:warm and consultative, max 200 words, greeting Hey {first_name}",
        "confidence": 0.93,
        "ae_id": "ae-sarah",
    }),
    ("email_max_words", {
        "type": "ae_preference",
        "preference_type": "email_max_words",
        "preference_value": "200",
        "content": "email_max_words:200",
        "confidence": 0.93,
        "ae_id": "ae-sarah",
    }),
    ("preferred_cta", {
        "type": "ae_preference",
        "preference_type": "preferred_cta",
        "preference_value": "discovery workshop",
        "content": "preferred_cta:discovery workshop",
        "confidence": 0.88,
        "ae_id": "ae-sarah",
    }),
    ("sign_off", {
        "type": "ae_preference",
        "preference_type": "sign_off",
        "preference_value": "Cheers, Sarah",
        "content": "sign_off:Cheers, Sarah",
        "confidence": 0.92,
        "ae_id": "ae-sarah",
    }),
]

for key, value in sarah_prefs:
    store.put(("ae_memories", "ae-sarah"), key, value)
print(f"Seeded {len(sarah_prefs)} preferences for ae-sarah")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Seed Account Context

# COMMAND ----------

account_context = [
    ("ACC-1001", "champion_promotion_mar2026", {
        "type": "account_context",
        "context_type": "champion_change",
        "content": "Sarah Chen was promoted to VP of IT Operations in March 2026 — she now has direct budget authority up to $2M",
        "confidence": 0.95,
        "ae_id": "ae-jamie",
        "account_id": "ACC-1001",
    }),
    ("ACC-1001", "bmc_demo_negative_feedback", {
        "type": "account_context",
        "context_type": "competitor_mentioned",
        "content": "BMC Helix had a demo with Meridian in March 2026 but feedback was negative — UI described as clunky",
        "confidence": 0.92,
        "ae_id": "ae-jamie",
        "account_id": "ACC-1001",
    }),
    ("ACC-1001", "budget_consolidation_mandate", {
        "type": "account_context",
        "context_type": "budget_freeze",
        "content": "Board mandate to reduce IT ops spend by 15% this fiscal year — champion sees platform consolidation as the path",
        "confidence": 0.88,
        "ae_id": "ae-jamie",
        "account_id": "ACC-1001",
    }),
    ("ACC-1002", "ciso_mttr_requirement", {
        "type": "account_context",
        "context_type": "technical_requirement",
        "content": "CISO Jennifer Walsh requires SOC team MTTR under 15 minutes — current average is 45 minutes",
        "confidence": 0.90,
        "ae_id": "ae-jamie",
        "account_id": "ACC-1002",
    }),
    ("ACC-1002", "palo_alto_discount", {
        "type": "account_context",
        "context_type": "competitor_mentioned",
        "content": "Palo Alto XSOAR offering aggressive discounting on the Apex deal",
        "confidence": 0.85,
        "ae_id": "ae-jamie",
        "account_id": "ACC-1002",
    }),
    ("ACC-1002", "champion_ai_triage_push", {
        "type": "account_context",
        "context_type": "sentiment_shift",
        "content": "Champion Michael Torres is pushing hard for AI-powered triage — his pet project with executive visibility",
        "confidence": 0.87,
        "ae_id": "ae-jamie",
        "account_id": "ACC-1002",
    }),
    ("ACC-1006", "champion_quiet_feb2026", {
        "type": "account_context",
        "context_type": "champion_change",
        "content": "James Liu (Head of Platform) went quiet in Feb 2026 — last known: building internal ROI business case, no budget approval from CEO",
        "confidence": 0.82,
        "ae_id": "ae-jamie",
        "account_id": "ACC-1006",
    }),
    ("ACC-1003", "cto_fast_timeline", {
        "type": "account_context",
        "context_type": "timeline_shift",
        "content": "CTO Amy Rodriguez wants to be live by August 2026 — fast timeline, no formal RFP yet",
        "confidence": 0.91,
        "ae_id": "ae-sarah",
        "account_id": "ACC-1003",
    }),
]

for account_id, key, value in account_context:
    store.put(("account_memories", account_id), key, value)
print(f"Seeded {len(account_context)} account context facts")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Seed Deal Decisions

# COMMAND ----------

decisions = [
    ("ae-jamie", "dec_opp3001_tco", {
        "type": "deal_decision",
        "opp_id": "OPP-3001",
        "recommendation": "Focus the executive briefing on 3-year TCO comparison vs current HP Service Manager + BMC stack",
        "ae_action": "accepted",
        "ae_feedback": "Good call — Kim is all about the numbers",
        "content": "accepted: Focus the executive briefing on 3-year TCO comparison vs current HP Service Manager + BMC stack",
        "ae_id": "ae-jamie",
    }),
    ("ae-jamie", "dec_opp3002_ai_triage", {
        "type": "deal_decision",
        "opp_id": "OPP-3002",
        "recommendation": "Lead with AI triage metrics in the email to CISO",
        "ae_action": "modified",
        "ae_feedback": "Good data but Jennifer is skeptical of AI claims — lead with the real incident detection story instead",
        "content": "modified: Lead with AI triage metrics in the email to CISO. Feedback: lead with real incident detection story instead",
        "ae_id": "ae-jamie",
    }),
    ("ae-jamie", "dec_opp3006_discount", {
        "type": "deal_decision",
        "opp_id": "OPP-3006",
        "recommendation": "Offer a 20% discount to re-engage James Liu at Atlas Cloud",
        "ae_action": "rejected",
        "ae_feedback": "Too early for discounts — James needs help building the internal business case first, not a lower price",
        "content": "rejected: Offer a 20% discount to re-engage James Liu at Atlas Cloud. Feedback: too early, help build business case first",
        "ae_id": "ae-jamie",
    }),
]

for ae_id, key, value in decisions:
    store.put(("deal_decisions", ae_id), key, value)
print(f"Seeded {len(decisions)} deal decisions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Verify

# COMMAND ----------

jamie_results = store.search(("ae_memories", "ae-jamie"), query="email preferences", limit=20)
sarah_results = store.search(("ae_memories", "ae-sarah"), query="email preferences", limit=20)
ctx_results = store.search(("account_memories", "ACC-1001"), query="champion budget competitor", limit=20)
dec_results = store.search(("deal_decisions", "ae-jamie"), query="recommendations", limit=20)

print("=" * 50)
print("Lakebase Memory Setup Complete")
print("=" * 50)
print(f"  Instance:          {LAKEBASE_INSTANCE_NAME}")
print(f"  AE Jamie prefs:    {len(jamie_results)} items")
print(f"  AE Sarah prefs:    {len(sarah_results)} items")
print(f"  Account context:   {len(ctx_results)} items (ACC-1001)")
print(f"  Deal decisions:    {len(dec_results)} items")
print()
print("Sample Jamie preference:")
if jamie_results:
    print(f"  [{jamie_results[0].key}]: {jamie_results[0].value}")
