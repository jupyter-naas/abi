#!/bin/sh
set -eu

if [ -z "${NEXUS_API_URL:-}" ]; then
  echo "ERROR: NEXUS_API_URL is required (example: https://api.example.com)"
  exit 1
fi

case "${NEXUS_API_URL}" in
  http://*|https://*) ;;
  *)
    echo "ERROR: NEXUS_API_URL must start with http:// or https://"
    exit 1
    ;;
esac

NEXUS_ENV="${NEXUS_ENV:-cloudflare}"
NEXUS_WS_PATH="${NEXUS_WS_PATH:-/ws/socket.io}"
NEXUS_FRONTEND_URL="${NEXUS_FRONTEND_URL:-}"

cat >/app/apps/web/public/runtime-config.js <<EOF
window.__NEXUS_RUNTIME_CONFIG__ = {
  apiUrl: "${NEXUS_API_URL}",
  env: "${NEXUS_ENV}",
  websocketPath: "${NEXUS_WS_PATH}",
  frontendUrl: "${NEXUS_FRONTEND_URL}"
};
EOF

exec "$@"
