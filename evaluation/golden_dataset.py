"""
Generate a golden evaluation dataset from the seeded demo data.

Creates realistic deal scenarios with expected outputs for AI judge evaluation.
Run as a Databricks notebook after seeding demo data (setup/04_seed_demo_data.py).

Databricks tech: Unity Catalog (Delta tables) + Serverless SQL
"""

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  GOLDEN EVALUATION SCENARIOS                                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝

eval_scenarios = [
    {
        "scenario_id": "EVAL-001",
        "opp_id": "OPP-3001",
        "account_id": "ACC-1001",
        "question": "What's the deal health on OPP-3001 (Meridian Health) and draft a follow-up email for the champion?",
        "expected_health_range": "65-85",
        "expected_risk_flags": ["CIO engagement low"],
        "expected_outreach_themes": ["ITSM consolidation", "board pressure on IT spend", "SOW revision"],
        "expected_champion_name": "Sarah Chen",
        "personalization_criteria": "Must reference the 3-tool consolidation discussion and board pressure from March 28 call",
    },
    {
        "scenario_id": "EVAL-002",
        "opp_id": "OPP-3002",
        "account_id": "ACC-1002",
        "question": "Analyze the Apex Financial security deal. What's our competitive position against Palo Alto?",
        "expected_health_range": "50-70",
        "expected_risk_flags": ["CISO skeptical", "3 competitors", "champion quiet on budget"],
        "expected_outreach_themes": ["AI-powered triage", "unified IT+Security", "financial services proof points"],
        "expected_champion_name": "Michael Torres",
        "personalization_criteria": "Must reference the AI triage demo and Michael's strategy to get CISO excited about AI",
    },
    {
        "scenario_id": "EVAL-003",
        "opp_id": "OPP-3003",
        "account_id": "ACC-1003",
        "question": "NovaTech wants to move fast on cloud migration. Draft an email to the CTO with a discovery workshop proposal.",
        "expected_health_range": "70-90",
        "expected_risk_flags": [],
        "expected_outreach_themes": ["API-first architecture", "fast timeline", "cloud migration"],
        "expected_champion_name": "Amy Rodriguez",
        "personalization_criteria": "Must reference CTO's August go-live target and their Django-based legacy system",
    },
    {
        "scenario_id": "EVAL-004",
        "opp_id": "OPP-3004",
        "account_id": "ACC-1004",
        "question": "The Pacific Retail POC is halfway through. Draft an email to get the SVP to review results before Freshworks undercuts us.",
        "expected_health_range": "55-75",
        "expected_risk_flags": ["Freshworks price pressure", "SVP hasn't seen POC"],
        "expected_outreach_themes": ["AI resolution speed", "30% faster resolution", "ITSM integration story"],
        "expected_champion_name": "Karen Wright",
        "personalization_criteria": "Must reference the 30% faster resolution metric from POC and Tom's advice about the AI+ITSM angle",
    },
    {
        "scenario_id": "EVAL-005",
        "opp_id": "OPP-3006",
        "account_id": "ACC-1006",
        "question": "Atlas Cloud champion went quiet. What happened and how do we re-engage?",
        "expected_health_range": "20-45",
        "expected_risk_flags": ["GHOSTING", "NO budget approval", "CEO disengaged"],
        "expected_outreach_themes": ["ROI business case", "platform consolidation", "former ServiceNow employee"],
        "expected_champion_name": "James Liu",
        "personalization_criteria": "Must reference James's need for ROI data and his background as former ServiceNow employee",
    },
]

eval_df = spark.createDataFrame(eval_scenarios)
eval_df.write.mode("overwrite").saveAsTable("gtm.eval.golden_dataset")

print(f"Golden dataset created with {eval_df.count()} scenarios in gtm.eval.golden_dataset")
