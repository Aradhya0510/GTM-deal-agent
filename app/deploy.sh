#!/usr/bin/env bash
#
# Deploy the main GTM Deal Intelligence app (v2 Command Center) to Databricks Apps.
#
# Reads local deployment config from ../.env (gitignored), renders a temporary
# app.yaml with real resource name + env vars, uploads unchanged sanitized
# Python sources, and deploys. The checked-in app/app.yaml stays
# placeholder-only so the public repo remains shareable.
#
# Usage: ./app/deploy.sh
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
: "${MAIN_APP_NAME:?MAIN_APP_NAME must be set in .env}"
: "${MAIN_APP_WORKSPACE_PATH:?MAIN_APP_WORKSPACE_PATH must be set in .env}"
: "${GTM_ENDPOINT:?GTM_ENDPOINT must be set in .env}"

echo ">> Deploying app '$MAIN_APP_NAME' using profile '$DATABRICKS_PROFILE'"
echo ">> Workspace path: $MAIN_APP_WORKSPACE_PATH"

RENDERED_YAML="$(mktemp -t gtm-app-yaml.XXXXXX)"
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
  - name: VS_ENDPOINT_NAME
    value: "${VS_ENDPOINT_NAME}"
  - name: APP_URL
    value: "${MAIN_APP_URL:-}"
YAML

echo ">> Rendered app.yaml:"
sed 's/^/   /' "$RENDERED_YAML"

FILES=(app.py requirements.txt)

echo ">> Uploading sources to $MAIN_APP_WORKSPACE_PATH"
for f in "${FILES[@]}"; do
  databricks --profile "$DATABRICKS_PROFILE" workspace import \
    "$MAIN_APP_WORKSPACE_PATH/$f" \
    --file "$SCRIPT_DIR/$f" --format AUTO --overwrite
  echo "   uploaded $f"
done

databricks --profile "$DATABRICKS_PROFILE" workspace import \
  "$MAIN_APP_WORKSPACE_PATH/app.yaml" \
  --file "$RENDERED_YAML" --format AUTO --overwrite
echo "   uploaded app.yaml (rendered from .env)"

if ! databricks --profile "$DATABRICKS_PROFILE" apps get "$MAIN_APP_NAME" >/dev/null 2>&1; then
  cat >&2 <<EOF
ERROR: Databricks app '$MAIN_APP_NAME' does not exist in this workspace.

Create it first, then re-run this script:
  databricks --profile $DATABRICKS_PROFILE apps create $MAIN_APP_NAME

Or set MAIN_APP_NAME in .env to the name of an existing app.
EOF
  exit 1
fi

echo ">> Triggering app deployment"
databricks --profile "$DATABRICKS_PROFILE" apps deploy "$MAIN_APP_NAME" \
  --source-code-path "$MAIN_APP_WORKSPACE_PATH"

echo ""
echo ">> Done. Check status with:"
echo "     databricks --profile $DATABRICKS_PROFILE apps get $MAIN_APP_NAME"
