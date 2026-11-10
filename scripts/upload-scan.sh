#!/bin/sh
# Uploads a scanner's JSON report to the incident tracker.
#
#   INCIDENTS_URL=http://localhost:8000 INCIDENTS_KEY=ops_... \
#     scripts/upload-scan.sh <trivy|gitleaks|hadolint> report.json [target] [commit-sha] [run-url]
#
# The key must have source "scanner" (Admin page > API keys). The report is sent unchanged: the server drops
# secret values itself, so nothing sensitive is stored. Set COMPLETE=false for a partial scan (it then never marks
# missing findings as fixed).
set -eu

scanner="${1:?scanner: trivy, gitleaks or hadolint}"
report="${2:?path to the JSON report}"
target="${3:-}"
ref="${4:-}"
run_url="${5:-}"
: "${INCIDENTS_URL:?set INCIDENTS_URL, for example http://localhost:8000}"
: "${INCIDENTS_KEY:?set INCIDENTS_KEY to an API key with source scanner}"

# --url-query adds URL-encoded query parameters while the report goes in the request body (curl 7.87 or newer).
curl --fail-with-body -sS -X POST "$INCIDENTS_URL/api/intake/scan/$scanner" \
  --url-query "target=$target" --url-query "ref=$ref" --url-query "run_url=$run_url" \
  --url-query "complete=${COMPLETE:-true}" \
  -H "X-API-Key: $INCIDENTS_KEY" -H "Content-Type: application/json" \
  --data-binary "@$report"
echo
