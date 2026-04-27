#!/usr/bin/env bash
#
# Log and deploy the GTM Deal Intelligence agent to Model Serving.
#
# Uploads deployment/agent.py + deployment/log_and_deploy_notebook.py to the
# workspace and submits a serverless job that logs the model and calls
# agents.deploy(). Config is passed via notebook widgets (notebook_task
# base_parameters), populated from ../.env.
#
# Usage: ./deployment/deploy_agent.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.example to .env and fill in your values." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DATABRICKS_PROFILE:?DATABRICKS_PROFILE must be set in .env}"
: "${UC_CATALOG:?UC_CATALOG must be set in .env}"
: "${UC_SCHEMA:?UC_SCHEMA must be set in .env}"
: "${LLM_ENDPOINT:?LLM_ENDPOINT must be set in .env}"
: "${SQL_WAREHOUSE_ID:?SQL_WAREHOUSE_ID must be set in .env}"
: "${MLFLOW_EXPERIMENT_NAME:?MLFLOW_EXPERIMENT_NAME must be set in .env}"
: "${LAKEBASE_INSTANCE_NAME:?LAKEBASE_INSTANCE_NAME must be set in .env}"
: "${LAKEBASE_PAT_SECRET_SCOPE:?LAKEBASE_PAT_SECRET_SCOPE must be set in .env}"
: "${LAKEBASE_PAT_SECRET_KEY:?LAKEBASE_PAT_SECRET_KEY must be set in .env}"
: "${AGENT_NOTEBOOK_WORKSPACE_PATH:?AGENT_NOTEBOOK_WORKSPACE_PATH must be set in .env}"

echo ">> Logging and deploying agent using profile '$DATABRICKS_PROFILE'"

AGENT_PY_PATH="$AGENT_NOTEBOOK_WORKSPACE_PATH/agent.py"
LOG_NB_PATH="$AGENT_NOTEBOOK_WORKSPACE_PATH/log_and_deploy"
LAKEBASE_PAT_SECRET="{{secrets/${LAKEBASE_PAT_SECRET_SCOPE}/${LAKEBASE_PAT_SECRET_KEY}}}"

echo ">> Uploading agent.py to $AGENT_PY_PATH"
databricks --profile "$DATABRICKS_PROFILE" workspace import \
  "$AGENT_PY_PATH" \
  --file "$SCRIPT_DIR/agent.py" --format AUTO --overwrite

echo ">> Uploading log_and_deploy notebook to $LOG_NB_PATH"
databricks --profile "$DATABRICKS_PROFILE" workspace import \
  "$LOG_NB_PATH" \
  --file "$SCRIPT_DIR/log_and_deploy_notebook.py" \
  --format SOURCE --language PYTHON --overwrite

# Build the job spec — base_parameters are passed as notebook widget values.
JOB_JSON=$(cat <<JSON
{
  "run_name": "gtm-agent-log-and-deploy",
  "tasks": [
    {
      "task_key": "log_and_deploy",
      "notebook_task": {
        "notebook_path": "$LOG_NB_PATH",
        "source": "WORKSPACE",
        "base_parameters": {
          "UC_CATALOG": "$UC_CATALOG",
          "UC_SCHEMA": "$UC_SCHEMA",
          "LLM_ENDPOINT": "$LLM_ENDPOINT",
          "MEMORY_LLM_ENDPOINT": "${MEMORY_LLM_ENDPOINT:-databricks-claude-haiku-4-5}",
          "DATABRICKS_EMBEDDING_ENDPOINT": "${DATABRICKS_EMBEDDING_ENDPOINT:-databricks-gte-large-en}",
          "SQL_WAREHOUSE_ID": "$SQL_WAREHOUSE_ID",
          "MLFLOW_EXPERIMENT_NAME": "$MLFLOW_EXPERIMENT_NAME",
          "LAKEBASE_INSTANCE_NAME": "$LAKEBASE_INSTANCE_NAME",
          "LAKEBASE_PAT_SECRET": "$LAKEBASE_PAT_SECRET",
          "AGENT_PY_WORKSPACE_PATH": "$AGENT_PY_PATH"
        }
      },
      "environment_key": "default"
    }
  ],
  "environments": [
    {
      "environment_key": "default",
      "spec": {
        "client": "2",
        "dependencies": [
          "mlflow>=3.6.0",
          "databricks-langchain[memory]>=0.17.0",
          "langgraph>=0.3",
          "langgraph-checkpoint-postgres>=2.0.5",
          "databricks-agents",
          "pydantic"
        ]
      }
    }
  ]
}
JSON
)

echo ">> Submitting job"
echo "$JOB_JSON" | databricks --profile "$DATABRICKS_PROFILE" jobs submit --json @/dev/stdin

echo ""
echo ">> Job submitted. Monitor progress in the Jobs UI or with:"
echo "     databricks --profile $DATABRICKS_PROFILE jobs list-runs --limit 5"
