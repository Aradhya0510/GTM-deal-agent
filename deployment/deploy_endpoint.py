"""
Deploy the GTM Deal Intelligence Agent to Databricks Model Serving.

Steps:
  1. Log the agent as an MLflow model
  2. Register in Unity Catalog
  3. Deploy to a serverless Model Serving endpoint

Databricks tech: MLflow 3.0 + Model Serving + Unity Catalog Model Registry
"""

import mlflow
from databricks.agents import deploy
from databricks.sdk import WorkspaceClient

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CONFIGURATION                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝

EXPERIMENT_NAME = "/gtm/deal-intelligence-agent"
MODEL_NAME = "gtm.agents.deal_intelligence"
ENDPOINT_NAME = "gtm-deal-intelligence"

w = WorkspaceClient()
mlflow.set_experiment(EXPERIMENT_NAME)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 1: Log the agent to MLflow                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝

print("Step 1: Logging agent to MLflow...")

with mlflow.start_run(run_name="gtm-agent-deploy") as run:
    model_info = mlflow.langchain.log_model(
        lc_model="src/servicenow_gtm_agent/serving/agent_model.py",
        name="gtm_agent",
        pip_requirements=[
            "langgraph>=0.2",
            "langchain-core>=0.3",
            "langchain-community>=0.3",
            "mlflow>=3.0",
            "databricks-sdk>=0.30",
            "databricks-agents>=0.10",
            "pydantic>=2.0",
            "pyyaml>=6.0",
        ],
    )
    run_id = run.info.run_id
    model_uri = model_info.model_uri
    print(f"  Run ID: {run_id}")
    print(f"  Model URI: {model_uri}")

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 2: Register in Unity Catalog                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝

print(f"\nStep 2: Registering model as {MODEL_NAME}...")

registered = mlflow.register_model(
    model_uri=model_uri,
    name=MODEL_NAME,
)
print(f"  Version: {registered.version}")

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 3: Deploy to Model Serving                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝

print(f"\nStep 3: Deploying to endpoint '{ENDPOINT_NAME}'...")

deployment = deploy(
    model_name=MODEL_NAME,
    version=registered.version,
    scale_to_zero=True,
    enable_feedback_ui=True,
    traffic_config={
        "canary_percent": 10,
        "rollout_hours": 48,
    },
)

print(f"\n  Endpoint URL:  {deployment.endpoint_url}")
print(f"  Review App:    {deployment.review_app_url}")
print(f"  Status:        Deployed (scale-to-zero enabled)")

print("\n" + "=" * 60)
print("Deployment complete.")
print(f"  Model:    {MODEL_NAME} v{registered.version}")
print(f"  Endpoint: {ENDPOINT_NAME}")
print("=" * 60)
