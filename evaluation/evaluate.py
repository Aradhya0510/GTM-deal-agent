"""
Agent Evaluation — MLflow evaluation with AI judges.

Runs the GTM agent against the golden dataset and evaluates:
  - Groundedness: are claims backed by retrieved data?
  - Relevance: is the response relevant to the deal context?
  - Personalization quality: specific signals used? (custom judge)
  - Safety: no hallucinated facts or PII leakage?

Databricks tech: MLflow 3.0 (evaluation) + Model Serving (AI judges)
                 + Agent Evaluation Framework
"""

import mlflow
from databricks.agents import evaluate
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CONFIGURATION                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝

EXPERIMENT_NAME = "/gtm/deal-intelligence-eval"
AGENT_ENDPOINT = "gtm-deal-intelligence"

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  LOAD EVALUATION DATA                                                    ║
# ╚══════════════════════════════════════════════════════════════════════════╝

eval_data = spark.table("gtm.eval.golden_dataset").toPandas()
print(f"Loaded {len(eval_data)} evaluation scenarios")

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CUSTOM JUDGE: Personalization Quality                                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

PERSONALIZATION_JUDGE_PROMPT = """
Rate this outreach email 1-5 on personalization quality.

5 = References a specific named insight from a recent call, connects to a
    stated business priority by name, includes a proof point from a comparable
    customer in the same industry. Every sentence grounded in data.
4 = References specific people and data points but misses one dimension
    (e.g., no industry-matched proof point).
3 = Some personalization but relies on generic patterns. Mentions names but
    doesn't connect insights to business outcomes.
2 = Mostly generic with one or two specific details sprinkled in.
1 = Fully generic email that could apply to any prospect.

Email output: {output}
Account context: {retrieved_context}
Expected personalization: {expected_personalization}

Return ONLY a JSON object: {"score": <1-5>, "rationale": "<1-2 sentences>"}
"""

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  RUN EVALUATION                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝

mlflow.set_experiment(EXPERIMENT_NAME)

with mlflow.start_run(run_name="eval-golden-dataset"):

    results = evaluate(
        model=AGENT_ENDPOINT,
        data=eval_data,
        model_type="databricks-agent",
        evaluators=["databricks"],
        evaluator_config={
            "databricks": {
                "metrics": [
                    "groundedness",
                    "relevance",
                    "retrieval_precision",
                    "safety",
                    "personalization_quality",
                ],
                "custom_judges": [
                    {
                        "name": "personalization_quality",
                        "judge_prompt": PERSONALIZATION_JUDGE_PROMPT,
                        "model": "databricks-claude-3-5-sonnet",
                    }
                ],
            }
        },
    )

    # ── Print Results ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    metrics = results.metrics
    for key in sorted(metrics.keys()):
        if "mean" in key:
            print(f"  {key:40s} {metrics[key]:.3f}")

    # ── Quality Gates ────────────────────────────────────────────────────
    print("\n" + "-" * 60)
    print("QUALITY GATES")
    print("-" * 60)

    gates = {
        "groundedness/mean": 0.85,
        "relevance/mean": 0.80,
        "personalization_quality/mean": 0.75,
        "safety/mean": 0.95,
    }

    all_passed = True
    for metric, threshold in gates.items():
        value = metrics.get(metric, 0)
        passed = value >= threshold
        status = "PASS" if passed else "FAIL"
        print(f"  {status:4s} | {metric:40s} {value:.3f} >= {threshold:.2f}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\nAll quality gates passed — ready for staging deployment.")
        mlflow.log_param("quality_gate", "PASSED")
    else:
        print("\nQuality gates FAILED — review results before promoting.")
        mlflow.log_param("quality_gate", "FAILED")
