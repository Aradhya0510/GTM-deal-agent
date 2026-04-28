#!/usr/bin/env bash
#
# Bootstrap UC objects required by the agent + apps.
# Uploads setup/bootstrap_uc_objects.py and submits a serverless job that
# creates flattened tables, UC functions, and VS indexes in
# {UC_CATALOG}.{UC_SCHEMA} matching deployment/agent.py expectations.
#
# Usage: ./deployment/deploy_bootstrap.sh
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
: "${VS_ENDPOINT_NAME:?VS_ENDPOINT_NAME must be set in .env}"
: "${AGENT_NOTEBOOK_WORKSPACE_PATH:?AGENT_NOTEBOOK_WORKSPACE_PATH must be set in .env}"

NB_PATH="$AGENT_NOTEBOOK_WORKSPACE_PATH/bootstrap_uc_objects"

echo ">> Bootstrapping UC objects in $UC_CATALOG.$UC_SCHEMA"
echo ">> Uploading notebook to $NB_PATH"

databricks --profile "$DATABRICKS_PROFILE" workspace import \
  "$NB_PATH" \
  --file "$REPO_ROOT/setup/bootstrap_uc_objects.py" \
  --format SOURCE --language PYTHON --overwrite

JOB_JSON=$(cat <<JSON
{
  "run_name": "gtm-uc-bootstrap",
  "tasks": [
    {
      "task_key": "bootstrap",
      "notebook_task": {
        "notebook_path": "$NB_PATH",
        "source": "WORKSPACE",
        "base_parameters": {
          "UC_CATALOG": "$UC_CATALOG",
          "UC_SCHEMA": "$UC_SCHEMA",
          "VS_ENDPOINT_NAME": "$VS_ENDPOINT_NAME",
          "EMBEDDING_ENDPOINT": "${DATABRICKS_EMBEDDING_ENDPOINT:-databricks-gte-large-en}"
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
          "databricks-vectorsearch>=0.40"
        ]
      }
    }
  ]
}
JSON
)

echo ">> Submitting bootstrap job"
echo "$JOB_JSON" | databricks --profile "$DATABRICKS_PROFILE" jobs submit --json @/dev/stdin
echo ""
echo ">> Bootstrap job submitted."
