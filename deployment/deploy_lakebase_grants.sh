#!/usr/bin/env bash
#
# Apply Lakebase Postgres grants for the agent + apps.
#
# Auto-discovers the service principal client_id of each Databricks App
# named in .env (APP_NAME for the showcase, MAIN_APP_NAME for the main GTM
# app), then submits deployment/lakebase_grant_permissions.py as a
# serverless job with those SP IDs as a widget parameter.
#
# Skips apps that don't exist in the workspace — useful if you're only
# deploying one of the two apps. If neither app exists, the script still
# applies the memory-table setup and PUBLIC grants but creates no per-SP
# roles.
#
# Usage: ./deployment/deploy_lakebase_grants.sh
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

NB_PATH="$AGENT_NOTEBOOK_WORKSPACE_PATH/lakebase_grant_permissions"
DATABASE_NAME="${LAKEBASE_DATABASE_NAME:-databricks_postgres}"

echo ">> Granting Lakebase permissions on $LAKEBASE_INSTANCE_NAME"

# Auto-discover SP client IDs from the apps in this workspace.
discover_sp_id() {
  local app_name="$1"
  if [[ -z "$app_name" ]]; then
    return 0
  fi
  if ! out=$(databricks --profile "$DATABRICKS_PROFILE" apps get "$app_name" 2>/dev/null); then
    echo "   (skip) app '$app_name' not found in workspace" >&2
    return 0
  fi
  # `apps get` returns JSON; pluck service_principal_client_id with python.
  echo "$out" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)
sp = d.get("service_principal_client_id", "")
if sp:
    print(sp)
'
}

SP_IDS=()
for n in "${APP_NAME:-}" "${MAIN_APP_NAME:-}"; do
  sp=$(discover_sp_id "$n" || true)
  if [[ -n "$sp" ]]; then
    echo "   discovered SP for app '$n': $sp"
    SP_IDS+=("$sp")
  fi
done

# Allow manual override via .env (comma-separated UUIDs in APP_SP_CLIENT_IDS).
# When set, this REPLACES the auto-discovered list.
if [[ -n "${APP_SP_CLIENT_IDS:-}" ]]; then
  echo "   APP_SP_CLIENT_IDS override from .env detected — using it instead"
  SP_IDS_CSV="$APP_SP_CLIENT_IDS"
else
  IFS=, eval 'SP_IDS_CSV="${SP_IDS[*]}"'
fi
echo "   final SP list: ${SP_IDS_CSV:-<none>}"

echo ">> Uploading notebook to $NB_PATH"
databricks --profile "$DATABRICKS_PROFILE" workspace import \
  "$NB_PATH" \
  --file "$SCRIPT_DIR/lakebase_grant_permissions.py" \
  --format SOURCE --language PYTHON --overwrite

JOB_JSON=$(cat <<JSON
{
  "run_name": "gtm-lakebase-grants",
  "tasks": [
    {
      "task_key": "grants",
      "notebook_task": {
        "notebook_path": "$NB_PATH",
        "source": "WORKSPACE",
        "base_parameters": {
          "LAKEBASE_INSTANCE_NAME": "$LAKEBASE_INSTANCE_NAME",
          "DATABASE_NAME": "$DATABASE_NAME",
          "APP_SP_CLIENT_IDS": "$SP_IDS_CSV",
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
          "langgraph-checkpoint-postgres>=2.0.5",
          "databricks-ai-bridge>=0.6.0",
          "psycopg[binary]>=3.1.0"
        ]
      }
    }
  ]
}
JSON
)

echo ">> Submitting grants job"
echo "$JOB_JSON" | databricks --profile "$DATABRICKS_PROFILE" jobs submit --json @/dev/stdin

echo ""
echo ">> Job submitted. Monitor progress with:"
echo "     databricks --profile $DATABRICKS_PROFILE jobs list-runs --limit 5"
echo ""
echo "   Look at the per-statement [OK] / [FAIL] log lines to see exactly"
echo "   which grants applied. Failures don't break the script — they just"
echo "   surface so you can debug them."
