# Databricks notebook source
# MAGIC %md
# MAGIC # Deploy GTM Streamlit App to Databricks Apps

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
username = w.current_user.me().user_name

APP_NAME = "gtm-deal-intelligence"
WORKSPACE_APP_DIR = f"/Workspace/Users/{username}/servicenow-gtm-agent/app"

print(f"User: {username}")
print(f"App: {APP_NAME}")
print(f"App dir: {WORKSPACE_APP_DIR}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deploy the App

# COMMAND ----------

import time

try:
    existing = w.apps.get(APP_NAME)
    print(f"App '{APP_NAME}' already exists. Updating...")
    app = w.apps.update(APP_NAME, description="GTM Deal Intelligence Agent — Powered by Databricks")
except Exception:
    print(f"Creating app '{APP_NAME}'...")
    app = w.apps.create_and_wait(
        name=APP_NAME,
        description="GTM Deal Intelligence Agent — Powered by Databricks",
        resources=[
            {
                "name": "deal-intelligence-endpoint",
                "serving_endpoint": {
                    "name": "agents_users-aradhya_chouhan-gtm_deal_intelligence_agent",
                    "permission": "CAN_QUERY",
                },
            },
        ],
    )

print(f"App: {app.name}")
print(f"URL: {app.url}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deploy latest source

# COMMAND ----------

deployment = w.apps.deploy_and_wait(
    app_name=APP_NAME,
    source_code_path=WORKSPACE_APP_DIR,
)

print(f"Deployment status: {deployment.status}")
print(f"App URL: https://e2-demo-west.cloud.databricks.com/apps/{APP_NAME}")

dbutils.notebook.exit(f"App deployed: {APP_NAME}")
