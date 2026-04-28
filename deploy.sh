#!/usr/bin/env bash
#
# Top-level dispatcher for all GTM Deal Intelligence deploy paths.
# All subcommands read config from ./.env (gitignored) — see .env.example.
#
# Usage:
#   ./deploy.sh bootstrap   — UC: seed Delta tables, UC functions, VS indexes (run once per env)
#   ./deploy.sh showcase    — Mission Control showcase Streamlit app
#   ./deploy.sh app         — Main GTM v2 Command Center Streamlit app
#   ./deploy.sh agent       — Log + redeploy the agent to Model Serving
#   ./deploy.sh lakebase    — Seed demo data into Lakebase Postgres
#   ./deploy.sh grants      — Grant Lakebase Postgres roles to Databricks identities
#   ./deploy.sh all-apps    — Both Streamlit apps (showcase + main)
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  grep -E '^#( |$)' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

[[ $# -eq 0 ]] && usage 1
case "$1" in
  bootstrap)
    exec "$REPO_ROOT/deployment/deploy_bootstrap.sh"
    ;;
  showcase)  exec "$REPO_ROOT/showcase/deploy.sh" ;;
  app)       exec "$REPO_ROOT/app/deploy.sh" ;;
  agent)     exec "$REPO_ROOT/deployment/deploy_agent.sh" ;;
  lakebase)  exec "$REPO_ROOT/deployment/deploy_lakebase.sh" ;;
  grants)    exec "$REPO_ROOT/deployment/deploy_lakebase_grants.sh" ;;
  all-apps)
    "$REPO_ROOT/showcase/deploy.sh"
    "$REPO_ROOT/app/deploy.sh"
    ;;
  -h|--help) usage 0 ;;
  *)
    echo "ERROR: unknown subcommand '$1'" >&2
    usage 1
    ;;
esac
