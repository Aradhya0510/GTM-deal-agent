# Databricks notebook source
# MAGIC %md
# MAGIC # GTM Deal Intelligence Agent — Log & Deploy
# MAGIC
# MAGIC Logs the agent from `agent.py`, registers in UC, and deploys to Model Serving.
# MAGIC
# MAGIC Memory now uses real Lakebase Postgres (`gtm-agent-memory` instance) via
# MAGIC `databricks-langchain[memory]` — no more Delta table workarounds.

# COMMAND ----------

import mlflow
from mlflow.models.resources import (
    DatabricksServingEndpoint, DatabricksFunction, DatabricksVectorSearchIndex,
    DatabricksSQLWarehouse, DatabricksTable,
)
from databricks_langchain import UCFunctionToolkit, VectorSearchRetrieverTool
from unitycatalog.ai.langchain.toolkit import UnityCatalogTool

CATALOG = "users"
SCHEMA = "aradhya_chouhan"
LLM_ENDPOINT = "databricks-claude-sonnet-4-6"
EXPERIMENT_NAME = "/Users/aradhya.chouhan@databricks.com/gtm-deal-intelligence"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.gtm_deal_intelligence_agent"

mlflow.set_experiment(EXPERIMENT_NAME)
print(f"Model: {MODEL_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build resources list for auth passthrough

# COMMAND ----------

uc_toolkit = UCFunctionToolkit(function_names=[
    f"{CATALOG}.{SCHEMA}.calculate_deal_health",
    f"{CATALOG}.{SCHEMA}.get_account_signals",
])
transcript_retriever = VectorSearchRetrieverTool(
    index_name=f"{CATALOG}.{SCHEMA}.gtm_transcripts_idx", num_results=4,
    columns=["transcript_id", "transcript_text", "call_date", "participants", "summary", "sentiment", "account_id"],
)
battlecard_retriever = VectorSearchRetrieverTool(
    index_name=f"{CATALOG}.{SCHEMA}.gtm_battlecards_idx", num_results=2,
    columns=["card_id", "content", "competitor", "use_case", "win_themes", "objection_handlers"],
)
deal_stories_retriever = VectorSearchRetrieverTool(
    index_name=f"{CATALOG}.{SCHEMA}.gtm_stories_idx", num_results=2,
    columns=["story_id", "narrative", "industry", "outcome", "key_moments", "competitor"],
)

all_tools = list(uc_toolkit.tools) + [transcript_retriever, battlecard_retriever, deal_stories_retriever]

MEMORY_LLM_ENDPOINT = "databricks-claude-haiku-4-5"
EMBEDDING_ENDPOINT = "databricks-gte-large-en"
SQL_WAREHOUSE_ID = "75fd8278393d07eb"

resources = [
    DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT),
    DatabricksServingEndpoint(endpoint_name=MEMORY_LLM_ENDPOINT),
    DatabricksServingEndpoint(endpoint_name=EMBEDDING_ENDPOINT),
    # SQL warehouse still needed for audit_agent_access Delta table
    DatabricksSQLWarehouse(warehouse_id=SQL_WAREHOUSE_ID),
    DatabricksTable(table_name=f"{CATALOG}.{SCHEMA}.audit_agent_access"),
    # Memory tables are now in Lakebase Postgres, not Delta — no DatabricksTable needed
]
for tool in all_tools:
    if isinstance(tool, UnityCatalogTool):
        resources.append(DatabricksFunction(function_name=tool.uc_function_name))
    elif isinstance(tool, VectorSearchRetrieverTool):
        resources.extend(tool.resources)

print(f"Resources: {len(resources)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log model (references agent.py, NOT this notebook)

# COMMAND ----------

model_info = mlflow.pyfunc.log_model(
    name="gtm_agent",
    python_model="/Workspace/Users/aradhya.chouhan@databricks.com/servicenow-gtm-agent/agent.py",
    resources=resources,
    pip_requirements=[
        "mlflow>=3.6.0",
        "databricks-langchain[memory]>=0.17.0",
        "langgraph>=0.3",
        "langgraph-checkpoint-postgres>=2.0.5",
        "databricks-agents",
        "pydantic",
    ],
    input_example={
        "input": [{"role": "user", "content": "What's the deal health on OPP-3001?"}]
    },
    registered_model_name=MODEL_NAME,
)
print(f"Model URI: {model_info.model_uri}")
print(f"Version: {model_info.registered_model_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deploy to Model Serving

# COMMAND ----------

from databricks.agents import deploy

deployment = deploy(
    model_name=MODEL_NAME,
    model_version=model_info.registered_model_version,
    environment_vars={
        "LAKEBASE_INSTANCE_NAME": "gtm-agent-memory",
        "LAKEBASE_PAT": "{{secrets/gtm-agent/sql-write-token}}",
        "DATABRICKS_EMBEDDING_ENDPOINT": "databricks-gte-large-en",
    },
)

print(f"Endpoint: {deployment.endpoint_name}")
print(f"Query endpoint: {deployment.query_endpoint}")

dbutils.notebook.exit(f"Deployed: {deployment.endpoint_name}")
