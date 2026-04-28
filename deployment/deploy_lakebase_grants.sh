#!/usr/bin/env bash
#
# Grant Lakebase Postgres permissions to all Databricks-auth'd identities,
# including the agent's Model Serving SP and the Databricks Apps SPs.
#
# Without this, the apps hit "password authentication failed" when connecting
# to Lakebase even though they have workspace-level CAN_CONNECT.
#
# Usage: ./deployment/deploy_lakebase_grants.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DATABRICKS_PROFILE:?DATABRICKS_PROFILE must be set in .env}"
: "${LAKEBASE_INSTANCE_NAME:?LAKEBASE_INSTANCE_NAME must be set in .env}"
: "${AGENT_NOTEBOOK_WORKSPACE_PATH:?AGENT_NOTEBOOK_WORKSPACE_PATH must be set in .env}"

NB_PATH="$AGENT_NOTEBOOK_WORKSPACE_PATH/lakebase_grant_permissions"

# Auto-discover Databricks Apps Service Principal client IDs so we can
# CREATE ROLE for each in Postgres. Apps SPs authenticate to Lakebase via
# OAuth tokens, but Postgres still requires a matching role to exist.
APP_NAMES=()
[[ -n "${APP_NAME:-}" ]] && APP_NAMES+=("$APP_NAME")
[[ -n "${MAIN_APP_NAME:-}" ]] && APP_NAMES+=("$MAIN_APP_NAME")

APP_SP_IDS=""
for app in "${APP_NAMES[@]}"; do
  client_id=$(databricks --profile "$DATABRICKS_PROFILE" apps get "$app" --output json 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('service_principal_client_id') or '')")
  if [[ -n "$client_id" ]]; then
    APP_SP_IDS="${APP_SP_IDS:+$APP_SP_IDS,}$client_id"
    echo ">> Discovered $app SP: $client_id"
  fi
done

echo ">> Granting Lakebase Postgres permissions on '$LAKEBASE_INSTANCE_NAME'"
echo ">> Uploading notebook to $NB_PATH"

databricks --profile "$DATABRICKS_PROFILE" workspace import \
  "$NB_PATH" \
  --file "$SCRIPT_DIR/lakebase_grant_permissions.py" \
  --format SOURCE --language PYTHON --overwrite

JOB_JSON=$(cat <<JSON
{
  "run_name": "lakebase-grant-permissions",
  "tasks": [
    {
      "task_key": "grant",
      "notebook_task": {
        "notebook_path": "$NB_PATH",
        "source": "WORKSPACE",
        "base_parameters": {
          "LAKEBASE_INSTANCE_NAME": "$LAKEBASE_INSTANCE_NAME",
          "DATABASE_NAME": "${LAKEBASE_DATABASE_NAME:-databricks_postgres}",
          "APP_SP_CLIENT_IDS": "$APP_SP_IDS"
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
          "langgraph-checkpoint-postgres>=2.0.5",
          "databricks-ai-bridge[memory]>=0.17.0"
        ]
      }
    }
  ]
}
JSON
)

echo ">> Submitting grant job"
echo "$JOB_JSON" | databricks --profile "$DATABRICKS_PROFILE" jobs submit --json @/dev/stdin
echo ""
echo ">> Done. The apps should reconnect on next request."
