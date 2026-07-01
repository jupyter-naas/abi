#!/usr/bin/env bash
# Headless bootstrap: wait for Coder, create the first (owner) user via the
# REST API, log in, and capture a session token for the provisioning demo.
set -euo pipefail

CODER_URL="${CODER_URL:-http://localhost:7080}"
EMAIL="${CODER_ADMIN_EMAIL:-admin@example.com}"
USERNAME="${CODER_ADMIN_USERNAME:-admin}"
PASSWORD="${CODER_ADMIN_PASSWORD:?set CODER_ADMIN_PASSWORD (see .env.example)}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> Waiting for Coder at ${CODER_URL} ..."
for _ in $(seq 1 90); do
  if curl -fsS "${CODER_URL}/api/v2/buildinfo" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "${CODER_URL}/api/v2/buildinfo" >/dev/null
echo "==> Coder is up: $(curl -fsS "${CODER_URL}/api/v2/buildinfo")"

echo "==> Creating first (owner) user (idempotent) ..."
curl -fsS -X POST "${CODER_URL}/api/v2/users/first" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\",\"name\":\"Admin\",\"trial\":false}" \
  >/dev/null 2>&1 || echo "    (first user already exists — continuing)"

echo "==> Logging in for a session token ..."
TOKEN="$(curl -fsS -X POST "${CODER_URL}/api/v2/users/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["session_token"])')"

echo "${TOKEN}" > "${HERE}/../.coder-token"
echo "==> Session token written to coder_prototype/.coder-token"
echo "    Use it with:  export CODER_SESSION_TOKEN=\$(cat coder_prototype/.coder-token)"
