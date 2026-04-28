#!/usr/bin/env bash
#
# Deploy the Mission Control showcase app to Databricks Apps.
#
# Reads local deployment config from ../.env (gitignored), renders a temporary
# app.yaml with real resource names + env vars, uploads unchanged sanitized
# Python sources, and deploys. The checked-in showcase/app.yaml stays
# placeholder-only so the public repo remains shareable.
#
# Usage: ./showcase/deploy.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.example to .env and fill in your values." >&2
  exit 1
fi

# Load .env (strip comments and blank lines, export all KEY=VALUE pairs)
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DATABRICKS_PROFILE:?DATABRICKS_PROFILE must be set in .env}"
: "${APP_NAME:?APP_NAME must be set in .env}"
: "${APP_WORKSPACE_PATH:?APP_WORKSPACE_PATH must be set in .env}"
: "${GTM_ENDPOINT:?GTM_ENDPOINT must be set in .env}"
: "${LAKEBASE_INSTANCE_NAME:?LAKEBASE_INSTANCE_NAME must be set in .env}"
: "${LAKEBASE_PAT_SECRET_SCOPE:?LAKEBASE_PAT_SECRET_SCOPE must be set in .env}"
: "${LAKEBASE_PAT_SECRET_KEY:?LAKEBASE_PAT_SECRET_KEY must be set in .env}"

echo ">> Deploying app '$APP_NAME' using profile '$DATABRICKS_PROFILE'"
echo ">> Workspace path: $APP_WORKSPACE_PATH"

# Render app.yaml into a temp file with real resource names + env vars.
# Databricks Apps supports `env:` with direct `value:` (not `value_from:`).
RENDERED_YAML="$(mktemp -t mc-app-yaml.XXXXXX)"
trap 'rm -f "$RENDERED_YAML"' EXIT

cat > "$RENDERED_YAML" <<YAML
command:
  - streamlit
  - run
  - app.py

resources:
  - name: deal-intelligence-endpoint
    serving_endpoint:
      name: ${GTM_ENDPOINT}
      permission: CAN_QUERY
  - name: lakebase-memory
    database:
      instance_name: ${LAKEBASE_INSTANCE_NAME}
      database_name: ${LAKEBASE_DATABASE_NAME:-databricks_postgres}
      permission: CAN_CONNECT_AND_CREATE
  - name: lakebase-pat
    secret:
      scope: ${LAKEBASE_PAT_SECRET_SCOPE}
      key: ${LAKEBASE_PAT_SECRET_KEY}
      permission: READ

env:
  - name: GTM_ENDPOINT
    value: "${GTM_ENDPOINT}"
  - name: UC_CATALOG
    value: "${UC_CATALOG}"
  - name: UC_SCHEMA
    value: "${UC_SCHEMA}"
  - name: SQL_WAREHOUSE_ID
    value: "${SQL_WAREHOUSE_ID}"
  - name: DATABRICKS_HOST
    value: "${DATABRICKS_HOST}"
  - name: DATABRICKS_WORKSPACE_ID
    value: "${DATABRICKS_WORKSPACE_ID}"
  - name: LAKEBASE_INSTANCE_NAME
    value: "${LAKEBASE_INSTANCE_NAME}"
  - name: LAKEBASE_PAT
    valueFrom: lakebase-pat
  - name: DATABRICKS_EMBEDDING_ENDPOINT
    value: "${DATABRICKS_EMBEDDING_ENDPOINT:-databricks-gte-large-en}"
  - name: LLM_ENDPOINT
    value: "${LLM_ENDPOINT:-databricks-claude-sonnet-4-6}"
  - name: VS_ENDPOINT_NAME
    value: "${VS_ENDPOINT_NAME}"
  - name: MLFLOW_EXPERIMENT_NAME
    value: "${MLFLOW_EXPERIMENT_NAME}"
YAML

echo ">> Rendered app.yaml:"
sed 's/^/   /' "$RENDERED_YAML"

# Upload unchanged sanitized Python sources + rendered app.yaml.
FILES=(app.py backend.py data.py styles.py components.py requirements.txt)

echo ">> Uploading sources to $APP_WORKSPACE_PATH"
for f in "${FILES[@]}"; do
  databricks --profile "$DATABRICKS_PROFILE" workspace import \
    "$APP_WORKSPACE_PATH/$f" \
    --file "$SCRIPT_DIR/$f" --format AUTO --overwrite
  echo "   uploaded $f"
done

databricks --profile "$DATABRICKS_PROFILE" workspace import \
  "$APP_WORKSPACE_PATH/app.yaml" \
  --file "$RENDERED_YAML" --format AUTO --overwrite
echo "   uploaded app.yaml (rendered from .env)"

if ! databricks --profile "$DATABRICKS_PROFILE" apps get "$APP_NAME" >/dev/null 2>&1; then
  cat >&2 <<EOF
ERROR: Databricks app '$APP_NAME' does not exist in this workspace.

Create it first, then re-run this script:
  databricks --profile $DATABRICKS_PROFILE apps create $APP_NAME

Or set APP_NAME in .env to the name of an existing app.
EOF
  exit 1
fi

echo ">> Triggering app deployment"
databricks --profile "$DATABRICKS_PROFILE" apps deploy "$APP_NAME" \
  --source-code-path "$APP_WORKSPACE_PATH"

echo ""
echo ">> Done. Check status with:"
echo "     databricks --profile $DATABRICKS_PROFILE apps get $APP_NAME"
