#!/usr/bin/env bash
# ABI Desktop dev server: detached supervisor + Python hot reload + crash restart.
#
# Usage (from repo root or anywhere):
#   ./libs/naas-abi/naas_abi/apps/desktop/scripts/dev.sh          # start detached
#   ./libs/naas-abi/naas_abi/apps/desktop/scripts/dev.sh stop     # stop supervisor + server
#   make dev-desktop
#
# Logs: ~/.abi-desktop/server.log
# Meta: ~/.abi-desktop/server.json (URL, port, worker PID)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

find_repo_root() {
  local dir="$1"
  while [[ "${dir}" != "/" ]]; do
    if [[ -f "${dir}/pyproject.toml" && -f "${dir}/Makefile" && -d "${dir}/libs/naas-abi-core" ]]; then
      echo "${dir}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done
  return 1
}

REPO_ROOT="$(find_repo_root "${DESKTOP_DIR}")" || {
  echo "error: could not locate ABI repository root from ${DESKTOP_DIR}" >&2
  exit 1
}

APPS_DIR="${REPO_ROOT}/libs/naas-abi/naas_abi/apps"
RUN_PY="${DESKTOP_DIR}/run.py"
DATA_DIR="${ABI_DESKTOP_HOME:-${HOME}/.abi-desktop}"
PORT="${ABI_DESKTOP_PORT:-54242}"
LOG_FILE="${DATA_DIR}/server.log"
SUPERVISOR_PID_FILE="${DATA_DIR}/dev-supervisor.pid"
INSTANCE_LOCK="${DATA_DIR}/instance.lock"
URL="http://127.0.0.1:${PORT}"

export ABI_DESKTOP_PORT="${PORT}"
export PYTHONPATH="${APPS_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

kill_pids() {
  local pids="$1"
  if [[ -z "${pids}" ]]; then
    return 0
  fi
  for pid in ${pids}; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
  sleep 0.3
  for pid in ${pids}; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
  done
}

stop_server() {
  mkdir -p "${DATA_DIR}"

  if [[ -f "${SUPERVISOR_PID_FILE}" ]]; then
    kill_pids "$(cat "${SUPERVISOR_PID_FILE}")"
    rm -f "${SUPERVISOR_PID_FILE}"
  fi

  if command -v lsof >/dev/null 2>&1; then
    kill_pids "$(lsof -ti ":${PORT}" 2>/dev/null || true)"
  fi

  if [[ -f "${DATA_DIR}/server.json" ]]; then
    local old_pid
    old_pid="$(DATA_DIR="${DATA_DIR}" python3 - <<'PY' 2>/dev/null || true
import json
import os
import pathlib

path = pathlib.Path(os.environ["DATA_DIR"]) / "server.json"
try:
    print(json.loads(path.read_text()).get("pid", ""))
except Exception:
    pass
PY
)"
    if [[ -n "${old_pid}" ]]; then
      kill_pids "${old_pid}"
    fi
  fi

  sleep 1
  rm -f "${INSTANCE_LOCK}"
  wait_for_port_free "${PORT}" 30 || {
    echo "error: port ${PORT} still busy after stop; set ABI_DESKTOP_PORT or quit the other process" >&2
    return 1
  }
}

detach_supervisor() {
  local inner="\"${BASH_SOURCE[0]}\" _supervisor_loop"
  if command -v setsid >/dev/null 2>&1; then
    setsid bash -c "${inner}" >>"${LOG_FILE}" 2>&1 &
  else
    # macOS lacks setsid; nohup + disown still survives agent shell exit.
    nohup bash -c "${inner}" >>"${LOG_FILE}" 2>&1 </dev/null &
  fi
  echo $!
}

wait_for_health() {
  local attempts="${1:-60}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl -sf "${URL}/api/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

port_is_free() {
  python3 - <<PY >/dev/null 2>&1
import socket
port = int("${1}")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", port))
PY
}

wait_for_port_free() {
  local attempts="${2:-30}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if port_is_free "${1}"; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

_supervisor_loop() {
  export ABI_DESKTOP_BROWSER=1
  export ABI_DESKTOP_RELOAD=1
  export ABI_DESKTOP_PORT="${PORT}"

  cd "${REPO_ROOT}"
  while true; do
    {
      echo ""
      echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) starting ABI Desktop dev server ==="
    } >>"${LOG_FILE}"

    set +e
    uv run python "${RUN_PY}" --browser-only --reload --no-open-browser >>"${LOG_FILE}" 2>&1
    exit_code=$?
    set -e

    {
      echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) server exited (${exit_code}), restart in 2s ==="
    } >>"${LOG_FILE}"
    sleep 2
  done
}

start_server() {
  stop_server || return 1
  mkdir -p "${DATA_DIR}"

  local sup_pid
  sup_pid="$(detach_supervisor)"
  echo "${sup_pid}" >"${SUPERVISOR_PID_FILE}"
  disown "${sup_pid}" 2>/dev/null || true

  if wait_for_health 60; then
    echo "ABI Desktop ready at ${URL}"
    echo "Supervisor PID ${sup_pid} (see ${SUPERVISOR_PID_FILE})"
    echo "Logs: ${LOG_FILE}"
    if [[ -f "${DATA_DIR}/server.json" ]]; then
      echo "Meta: ${DATA_DIR}/server.json"
    fi
    return 0
  fi

  echo "error: server did not become healthy; check ${LOG_FILE}" >&2
  return 1
}

case "${1:-start}" in
  stop)
    stop_server
    echo "ABI Desktop dev server stopped."
    ;;
  _supervisor_loop)
    _supervisor_loop
    ;;
  start | "")
    start_server
    ;;
  *)
    echo "usage: $0 [start|stop]" >&2
    exit 1
    ;;
esac
