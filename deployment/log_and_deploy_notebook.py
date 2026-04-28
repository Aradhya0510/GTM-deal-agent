# Databricks notebook source
# MAGIC %md
# MAGIC # GTM Deal Intelligence Agent — Log & Deploy
# MAGIC
# MAGIC Logs the agent from `agent.py`, registers in UC, and deploys to Model Serving.
# MAGIC
# MAGIC Memory uses real Lakebase Postgres via `databricks-langchain[memory]`.

# COMMAND ----------

import os

import mlflow
from mlflow.models.resources import (
    DatabricksServingEndpoint, DatabricksFunction, DatabricksVectorSearchIndex,
    DatabricksSQLWarehouse, DatabricksTable,
)
from databricks_langchain import UCFunctionToolkit, VectorSearchRetrieverTool
from unitycatalog.ai.langchain.toolkit import UnityCatalogTool

# ── Configuration via notebook widgets ──
# When run as a job, deployment/deploy_agent.sh populates these from .env.
# When run interactively, set the widget values in the notebook UI.
dbutils.widgets.text("UC_CATALOG", "")
dbutils.widgets.text("UC_SCHEMA", "")
dbutils.widgets.text("LLM_ENDPOINT", "databricks-claude-sonnet-4-6")
dbutils.widgets.text("MEMORY_LLM_ENDPOINT", "databricks-claude-haiku-4-5")
dbutils.widgets.text("DATABRICKS_EMBEDDING_ENDPOINT", "databricks-gte-large-en")
dbutils.widgets.text("SQL_WAREHOUSE_ID", "")
dbutils.widgets.text("MLFLOW_EXPERIMENT_NAME", "")
dbutils.widgets.text("LAKEBASE_INSTANCE_NAME", "")
dbutils.widgets.text("LAKEBASE_PAT_SECRET", "")  # format: {{secrets/scope/key}}
dbutils.widgets.text("AGENT_PY_WORKSPACE_PATH", "")  # e.g. /Workspace/Users/.../agent.py

CATALOG = dbutils.widgets.get("UC_CATALOG")
SCHEMA = dbutils.widgets.get("UC_SCHEMA")
LLM_ENDPOINT = dbutils.widgets.get("LLM_ENDPOINT")
EXPERIMENT_NAME = dbutils.widgets.get("MLFLOW_EXPERIMENT_NAME")
MODEL_NAME = f"{CATALOG}.{SCHEMA}.gtm_deal_intelligence_agent"

assert CATALOG and SCHEMA, "UC_CATALOG and UC_SCHEMA widgets must be set"
assert EXPERIMENT_NAME, "MLFLOW_EXPERIMENT_NAME widget must be set"

# agent.py reads everything from os.environ. mlflow.pyfunc.log_model executes
# agent.py to capture the model — without these env vars set, the agent's
# UCFunctionToolkit and VectorSearchRetrieverTool initialize with empty fully
# qualified names and fail at import time. Export everything before logging.
os.environ["UC_CATALOG"] = CATALOG
os.environ["UC_SCHEMA"] = SCHEMA
os.environ["LLM_ENDPOINT"] = LLM_ENDPOINT
os.environ["MEMORY_LLM_ENDPOINT"] = dbutils.widgets.get("MEMORY_LLM_ENDPOINT")
os.environ["DATABRICKS_EMBEDDING_ENDPOINT"] = dbutils.widgets.get("DATABRICKS_EMBEDDING_ENDPOINT")
os.environ["SQL_WAREHOUSE_ID"] = dbutils.widgets.get("SQL_WAREHOUSE_ID")
os.environ["LAKEBASE_INSTANCE_NAME"] = dbutils.widgets.get("LAKEBASE_INSTANCE_NAME")
# LAKEBASE_PAT is needed at log time only as a placeholder; real value is
# substituted at serving time by Model Serving from the secret reference.
os.environ.setdefault("LAKEBASE_PAT", "placeholder-for-log-time")

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

MEMORY_LLM_ENDPOINT = dbutils.widgets.get("MEMORY_LLM_ENDPOINT")
EMBEDDING_ENDPOINT = dbutils.widgets.get("DATABRICKS_EMBEDDING_ENDPOINT")
SQL_WAREHOUSE_ID = dbutils.widgets.get("SQL_WAREHOUSE_ID")
assert SQL_WAREHOUSE_ID, "SQL_WAREHOUSE_ID widget must be set"

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

AGENT_PY_PATH = dbutils.widgets.get("AGENT_PY_WORKSPACE_PATH")
assert AGENT_PY_PATH, "AGENT_PY_WORKSPACE_PATH widget must be set"

model_info = mlflow.pyfunc.log_model(
    name="gtm_agent",
    python_model=AGENT_PY_PATH,
    resources=resources,
    pip_requirements=[
        "mlflow>=3.6.0",
        "databricks-langchain[memory]>=0.17.0",
        "langgraph>=1.1.7",
        "langgraph-checkpoint-postgres>=2.0.5",
        "databricks-agents",
        "pydantic",
        "unitycatalog-langchain[databricks]>=0.3.0",
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

LAKEBASE_INSTANCE_NAME = dbutils.widgets.get("LAKEBASE_INSTANCE_NAME")
LAKEBASE_PAT_SECRET = dbutils.widgets.get("LAKEBASE_PAT_SECRET")
assert LAKEBASE_INSTANCE_NAME, "LAKEBASE_INSTANCE_NAME widget must be set"
assert LAKEBASE_PAT_SECRET, "LAKEBASE_PAT_SECRET widget must be set (format: {{secrets/scope/key}})"

deployment = deploy(
    model_name=MODEL_NAME,
    model_version=model_info.registered_model_version,
    environment_vars={
        "UC_CATALOG": CATALOG,
        "UC_SCHEMA": SCHEMA,
        "LLM_ENDPOINT": LLM_ENDPOINT,
        "MEMORY_LLM_ENDPOINT": MEMORY_LLM_ENDPOINT,
        "SQL_WAREHOUSE_ID": SQL_WAREHOUSE_ID,
        "LAKEBASE_INSTANCE_NAME": LAKEBASE_INSTANCE_NAME,
        "LAKEBASE_PAT": LAKEBASE_PAT_SECRET,
        "DATABRICKS_EMBEDDING_ENDPOINT": EMBEDDING_ENDPOINT,
    },
)

print(f"Endpoint: {deployment.endpoint_name}")
print(f"Query endpoint: {deployment.query_endpoint}")

dbutils.notebook.exit(f"Deployed: {deployment.endpoint_name}")
