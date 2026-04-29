#!/usr/bin/env bash
#
# Top-level dispatcher for all GTM Deal Intelligence deploy paths.
# All subcommands read config from ./.env (gitignored) — see .env.example.
#
# Usage:
#   ./deploy.sh bootstrap    — Provision UC catalog/schema/tables/functions/VS indexes
#   ./deploy.sh agent        — Log + redeploy the agent to Model Serving
#   ./deploy.sh lakebase     — Seed demo data into Lakebase Postgres memory
#   ./deploy.sh app          — Main GTM v2 Command Center Streamlit app
#   ./deploy.sh showcase     — Mission Control showcase Streamlit app
#   ./deploy.sh all-apps     — Both Streamlit apps (showcase + main)
#
# Recommended order for a fresh workspace:
#   1. ./deploy.sh bootstrap    (UC objects must exist before the agent logs)
#   2. ./deploy.sh lakebase     (memory tables)
#   3. ./deploy.sh agent        (log + register + deploy to Model Serving)
#   4. ./deploy.sh app          (or showcase, or both via all-apps)
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  grep -E '^#( |$)' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

[[ $# -eq 0 ]] && usage 1
case "$1" in
  bootstrap) exec "$REPO_ROOT/deployment/deploy_bootstrap.sh" ;;
  agent)     exec "$REPO_ROOT/deployment/deploy_agent.sh" ;;
  lakebase)  exec "$REPO_ROOT/deployment/deploy_lakebase.sh" ;;
  app)       exec "$REPO_ROOT/app/deploy.sh" ;;
  showcase)  exec "$REPO_ROOT/showcase/deploy.sh" ;;
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
