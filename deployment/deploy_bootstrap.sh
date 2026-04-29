#!/usr/bin/env bash
#
# Bootstrap UC objects for the GTM Deal Intelligence Agent.
#
# Uploads setup/bootstrap_uc_objects.py to the workspace and submits a
# serverless job that creates the catalog, schema, Delta tables (with seed
# data), UC functions, and Vector Search indexes — all under
# {UC_CATALOG}.{UC_SCHEMA}, matching what agent.py expects. Config is passed
# via notebook widgets (notebook_task base_parameters), populated from ../.env.
#
# Replaces the older multi-file `setup/0X_*.{sql,py}` scripts which created
# objects across multiple schemas (`gtm.crm`, `gtm.tools`, `gtm.vectors`,
# `gtm.audit`, etc.) that didn't match the agent's flat layout.
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

# Optional: BOOTSTRAP_CREATE_CATALOG (default true). Set to "false" in .env when
# the catalog already exists with a managed location the metastore can't
# re-validate on a re-run (workspace-specific bypass).
BOOTSTRAP_CREATE_CATALOG="${BOOTSTRAP_CREATE_CATALOG:-true}"

NB_PATH="$AGENT_NOTEBOOK_WORKSPACE_PATH/bootstrap_uc_objects"

echo ">> Bootstrapping UC objects in $UC_CATALOG.$UC_SCHEMA"
echo ">> Profile:        $DATABRICKS_PROFILE"
echo ">> VS endpoint:    $VS_ENDPOINT_NAME"
echo ">> Create catalog: $BOOTSTRAP_CREATE_CATALOG"
echo ">> Uploading notebook to $NB_PATH"

databricks --profile "$DATABRICKS_PROFILE" workspace import \
  "$NB_PATH" \
  --file "$REPO_ROOT/setup/bootstrap_uc_objects.py" \
  --format SOURCE --language PYTHON --overwrite

JOB_JSON=$(cat <<JSON
{
  "run_name": "gtm-bootstrap-uc-objects",
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
          "DATABRICKS_EMBEDDING_ENDPOINT": "${DATABRICKS_EMBEDDING_ENDPOINT:-databricks-gte-large-en}",
          "CREATE_CATALOG": "$BOOTSTRAP_CREATE_CATALOG"
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
echo ">> Job submitted. Monitor progress in the Jobs UI or with:"
echo "     databricks --profile $DATABRICKS_PROFILE jobs list-runs --limit 5"
