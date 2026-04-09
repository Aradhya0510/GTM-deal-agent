# Databricks notebook source
# MAGIC %md
# MAGIC # GTM Agent Evaluation — AI Judges
# MAGIC
# MAGIC Runs the deployed agent against golden scenarios and evaluates with MLflow scorers.
# MAGIC
# MAGIC **Powered by:** MLflow 3.0 Evaluation + Model Serving + AI Judges

# COMMAND ----------

import mlflow
import pandas as pd
import json

EXPERIMENT_NAME = "/Users/aradhya.chouhan@databricks.com/gtm-deal-intelligence-eval"
EP_NAME = "agents_users-aradhya_chouhan-gtm_deal_intelligence_agent"
JUDGE_MODEL = "databricks-claude-sonnet-4-6"

mlflow.set_experiment(EXPERIMENT_NAME)
print(f"Endpoint: {EP_NAME}")
print(f"Judge model: {JUDGE_MODEL}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Golden Evaluation Dataset

# COMMAND ----------

eval_data = pd.DataFrame([
    {
        "request": "What's the deal health on OPP-3001 (Meridian Health)? Give me the score, risk flags, and key contacts.",
        "expected_facts": "Health score around 76. Champion is Sarah Chen. Stage is Negotiation. Amount $1.8M. Competing with ServiceNow and BMC Helix. Key contacts include Dr. Robert Kim (CIO) and Lisa Patel.",
    },
    {
        "request": "Analyze the Apex Financial security deal (OPP-3002). What's our competitive position against Palo Alto and Splunk?",
        "expected_facts": "Stage is Proposal. Amount $3.2M. 3 competitors: Splunk, Palo Alto, ServiceNow. Champion is Michael Torres (VP Engineering). CISO Jennifer Walsh is skeptical. Key battlecard theme: unified IT+Security platform, AI triage reduces false positives by 80%.",
    },
    {
        "request": "NovaTech (OPP-3003) wants to move fast on cloud migration. Draft a short email to the CTO proposing a discovery workshop.",
        "expected_facts": "CTO is Amy Rodriguez. Stage is Discovery. Budget $500K-600K. August go-live target. Legacy Django ticketing system. We're the first vendor. API-first architecture is our differentiator.",
    },
    {
        "request": "The Pacific Retail POC (OPP-3004) is halfway through. Freshworks is undercutting us on price. What should we do?",
        "expected_facts": "POC showing 30% faster resolution with AI. Karen Wright (SVP CX) hasn't seen POC yet. Tom Harris recommends focusing on AI story + ITSM integration. Freshworks bid 40% lower. Stage is Technical Validation.",
    },
    {
        "request": "Atlas Cloud champion (OPP-3006) went quiet. What happened and how do we re-engage James Liu?",
        "expected_facts": "James Liu is Head of Platform, former ServiceNow employee. CEO Nina Sharma hasn't approved budget. Low health score. James needs ROI data for business case. Competing with Atlassian and PagerDuty. Discovery stage.",
    },
])

print(f"Evaluation dataset: {len(eval_data)} scenarios")
eval_data

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query the Agent

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

def query_agent(question: str) -> str:
    """Query the deployed agent and return the text response."""
    try:
        response = w.api_client.do(
            "POST",
            f"/serving-endpoints/{EP_NAME}/invocations",
            body={"input": [{"role": "user", "content": question}]},
        )
        # Extract text from ResponsesAgent output
        texts = []
        for item in response.get("output", []):
            if isinstance(item, dict) and item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        texts.append(content["text"])
        return "\n".join(texts) if texts else json.dumps(response)
    except Exception as e:
        return f"ERROR: {str(e)}"

# Run all queries
print("Querying agent for each scenario...")
responses = []
for i, row in eval_data.iterrows():
    print(f"\n  [{i+1}/{len(eval_data)}] {row['request'][:60]}...")
    resp = query_agent(row["request"])
    responses.append(resp)
    print(f"    Response length: {len(resp)} chars")

eval_data["response"] = responses
print(f"\nAll {len(responses)} queries completed.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Evaluate with AI Judges (MLflow Scorers)

# COMMAND ----------

from mlflow.genai.scorers import Guidelines, RetrievalGroundedness, Safety

# Custom personalization scorer
personalization_guidelines = Guidelines(
    name="personalization_quality",
    guidelines=(
        "The response should demonstrate personalization by:\n"
        "1. Referencing specific people by name (not generic 'the champion')\n"
        "2. Citing specific numbers, dates, or metrics from CRM data\n"
        "3. Connecting insights to business outcomes relevant to the account\n"
        "4. Including proof points or competitive intel specific to the deal context\n"
        "5. If drafting outreach, grounding every sentence in a specific signal\n\n"
        "Score YES if the response uses at least 3 of these 5 personalization signals. Score NO if generic."
    ),
    model=f"endpoints:/{JUDGE_MODEL}",
)

# Groundedness scorer
groundedness_guidelines = Guidelines(
    name="groundedness",
    guidelines=(
        "The response should only make factual claims that are supported by the tool results "
        "(CRM data, call transcripts, battlecards, deal stories). "
        "Score YES if all key claims (names, numbers, stages, risk flags) are grounded in retrieved data. "
        "Score NO if the response hallucinated facts not present in the data."
    ),
    model=f"endpoints:/{JUDGE_MODEL}",
)

# Actionability scorer
actionability_guidelines = Guidelines(
    name="actionability",
    guidelines=(
        "The response should provide specific, actionable next steps — not generic advice. "
        "Examples of actionable: 'Send the TCO model to Sarah by April 10' or 'Schedule a call with the CISO to address AI skepticism'. "
        "Examples of NOT actionable: 'Follow up soon' or 'Consider reaching out'. "
        "Score YES if the response includes at least 2 specific actionable recommendations with names/dates."
    ),
    model=f"endpoints:/{JUDGE_MODEL}",
)

safety_scorer = Safety(model=f"endpoints:/{JUDGE_MODEL}")

print("Scorers configured: personalization, groundedness, actionability, safety")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run MLflow Evaluation

# COMMAND ----------

# Build evaluation dataframe — inputs must be dicts, not plain strings
eval_df = pd.DataFrame({
    "inputs": [{"query": q} for q in eval_data["request"].tolist()],
    "outputs": [{"response": r} for r in eval_data["response"].tolist()],
    "expected_facts": eval_data["expected_facts"].tolist(),
})

with mlflow.start_run(run_name="gtm-agent-eval-golden"):
    results = mlflow.genai.evaluate(
        data=eval_df,
        predict_fn=None,  # We already have outputs
        scorers=[
            personalization_guidelines,
            groundedness_guidelines,
            actionability_guidelines,
            safety_scorer,
        ],
    )

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    metrics = results.metrics
    for key in sorted(metrics.keys()):
        print(f"  {key:45s} {metrics[key]}")

    # Quality gates
    print("\n" + "-" * 60)
    print("QUALITY GATES")
    print("-" * 60)

    gates = {
        "personalization_quality/percentage": 0.80,
        "groundedness/percentage": 0.80,
        "actionability/percentage": 0.60,
        "safety/percentage": 1.0,
    }

    all_passed = True
    for metric, threshold in gates.items():
        value = metrics.get(metric, 0)
        passed = value >= threshold
        status = "PASS" if passed else "FAIL"
        print(f"  {status:4s} | {metric:45s} {value:.2f} >= {threshold:.2f}")
        if not passed:
            all_passed = False

    gate_status = "PASSED" if all_passed else "FAILED"
    mlflow.log_param("quality_gate", gate_status)
    print(f"\nOverall: {gate_status}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Per-Scenario Results

# COMMAND ----------

results_table = results.tables["eval_results"]
display(results_table)

# COMMAND ----------

summary = f"Eval complete: {len(eval_data)} scenarios, gate={gate_status}"
print(summary)
dbutils.notebook.exit(summary)
