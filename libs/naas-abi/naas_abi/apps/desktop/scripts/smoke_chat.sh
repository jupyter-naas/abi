#!/usr/bin/env bash
# Manual chat smoke test against a running ABI Desktop instance.
# Skipped in CI — requires a live opencode serve and (for cloud models) API keys.
#
# Usage:
#   ./scripts/smoke_chat.sh
#   ABI_DESKTOP_URL=http://127.0.0.1:55031 ./scripts/smoke_chat.sh
#   SMOKE_MODEL=ollama/qwen2.5-coder:7b ./scripts/smoke_chat.sh

set -euo pipefail

BASE_URL="${ABI_DESKTOP_URL:-http://127.0.0.1:55031}"
MODEL="${SMOKE_MODEL:-ollama/qwen2.5-coder:7b}"
PROMPT="${SMOKE_PROMPT:-Reply with exactly: pong}"
SECTION="${SMOKE_SECTION:-code}"
MAX_TIME="${SMOKE_MAX_TIME:-120}"

echo "==> health"
curl -sf "${BASE_URL}/api/health" | python3 -m json.tool

echo "==> doctor"
curl -sf "${BASE_URL}/api/doctor" | python3 -m json.tool

echo "==> create chat (section=${SECTION}, model=${MODEL})"
CHAT_JSON=$(curl -sf -X POST "${BASE_URL}/api/chats" \
  -H 'Content-Type: application/json' \
  -d "{\"title\":\"smoke\",\"section\":\"${SECTION}\",\"model\":\"${MODEL}\"}")
CHAT_ID=$(echo "${CHAT_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "chat_id=${CHAT_ID}"

echo "==> send message (SSE, exit on complete/end)"
curl -sf -N -X POST "${BASE_URL}/api/chats/${CHAT_ID}/messages" \
  -H 'Content-Type: application/json' \
  -d "{\"text\":\"${PROMPT}\",\"model\":\"${MODEL}\"}" \
  --max-time "${MAX_TIME}" | python3 -u -c "
import json
import sys

for line in sys.stdin:
    sys.stdout.write(line)
    sys.stdout.flush()
    if not line.startswith('data: '):
        continue
    try:
        evt = json.loads(line[6:])
    except json.JSONDecodeError:
        continue
    kind = evt.get('type')
    if kind == 'error':
        print('smoke: error event', evt, file=sys.stderr)
        raise SystemExit(1)
    if kind in ('complete', 'end'):
        raise SystemExit(0)

print('smoke: stream ended without complete/end', file=sys.stderr)
raise SystemExit(1)
"

echo
echo "==> done"
