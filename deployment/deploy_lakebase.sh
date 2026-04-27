#!/usr/bin/env bash
#
# Seed demo data into the Lakebase Postgres memory instance.
#
# Uploads deployment/lakebase_memory_setup.py to the workspace and submits a
# serverless job that calls DatabricksStore.put() with the seed AE profiles,
# account contexts, and deal decisions. Config is passed via notebook widgets,
# populated from ../.env.
#
# Usage: ./deployment/deploy_lakebase.sh
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
: "${LAKEBASE_INSTANCE_NAME:?LAKEBASE_INSTANCE_NAME must be set in .env}"
: "${AGENT_NOTEBOOK_WORKSPACE_PATH:?AGENT_NOTEBOOK_WORKSPACE_PATH must be set in .env}"

NB_PATH="$AGENT_NOTEBOOK_WORKSPACE_PATH/lakebase_memory_setup"

echo ">> Seeding Lakebase instance '$LAKEBASE_INSTANCE_NAME' using profile '$DATABRICKS_PROFILE'"
echo ">> Uploading notebook to $NB_PATH"

databricks --profile "$DATABRICKS_PROFILE" workspace import \
  "$NB_PATH" \
  --file "$SCRIPT_DIR/lakebase_memory_setup.py" \
  --format SOURCE --language PYTHON --overwrite

JOB_JSON=$(cat <<JSON
{
  "run_name": "lakebase-memory-seed",
  "tasks": [
    {
      "task_key": "seed",
      "notebook_task": {
        "notebook_path": "$NB_PATH",
        "source": "WORKSPACE",
        "base_parameters": {
          "LAKEBASE_INSTANCE_NAME": "$LAKEBASE_INSTANCE_NAME",
          "DATABRICKS_EMBEDDING_ENDPOINT": "${DATABRICKS_EMBEDDING_ENDPOINT:-databricks-gte-large-en}"
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
          "databricks-langchain[memory]>=0.17.0",
          "langgraph-checkpoint-postgres>=2.0.5"
        ]
      }
    }
  ]
}
JSON
)

echo ">> Submitting seed job"
echo "$JOB_JSON" | databricks --profile "$DATABRICKS_PROFILE" jobs submit --json @/dev/stdin

echo ""
echo ">> Job submitted. Monitor progress with:"
echo "     databricks --profile $DATABRICKS_PROFILE jobs list-runs --limit 5"
