#!/usr/bin/env bash
# Idempotent ABI Desktop dev server bootstrap.
# Equivalent to dev.sh start — exits 0 when http://127.0.0.1:54242/api/health is OK.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/dev.sh" start "$@"
