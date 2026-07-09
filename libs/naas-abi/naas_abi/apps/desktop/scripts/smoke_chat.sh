#!/usr/bin/env bash
# Manual chat smoke test against a running ABI Desktop instance.
# Skipped in CI — requires a live opencode serve and (for cloud models) API keys.
#
# Usage:
#   ./scripts/smoke_chat.sh
#   ABI_DESKTOP_URL=http://127.0.0.1:55031 ./scripts/smoke_chat.sh
#   SMOKE_MODEL=ollama/gemma4:latest ./scripts/smoke_chat.sh

set -euo pipefail

BASE_URL="${ABI_DESKTOP_URL:-http://127.0.0.1:55031}"
MODEL="${SMOKE_MODEL:-ollama/gemma4:latest}"
PROMPT="${SMOKE_PROMPT:-Say hello in one word}"

echo "==> health"
curl -sf "${BASE_URL}/api/health" | python3 -m json.tool

echo "==> doctor"
curl -sf "${BASE_URL}/api/doctor" | python3 -m json.tool

echo "==> create chat (model=${MODEL})"
CHAT_JSON=$(curl -sf -X POST "${BASE_URL}/api/chats" \
  -H 'Content-Type: application/json' \
  -d "{\"title\":\"smoke\",\"section\":\"chat\",\"model\":\"${MODEL}\"}")
CHAT_ID=$(echo "${CHAT_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "chat_id=${CHAT_ID}"

echo "==> send message (SSE)"
curl -sf -N -X POST "${BASE_URL}/api/chats/${CHAT_ID}/messages" \
  -H 'Content-Type: application/json' \
  -d "{\"text\":\"${PROMPT}\",\"model\":\"${MODEL}\"}" \
  --max-time 120

echo
echo "==> done"
