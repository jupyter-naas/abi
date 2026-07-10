#!/usr/bin/env bash
# ABI Desktop dev server: detached supervisor + Python hot reload + crash restart.
#
# Usage (from repo root or anywhere):
#   ./libs/naas-abi/naas_abi/apps/desktop/scripts/dev.sh          # start (idempotent)
#   ./libs/naas-abi/naas_abi/apps/desktop/scripts/dev.sh status   # health + PID
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
START_LOCK_FILE="${DATA_DIR}/dev-start.lock"
INSTANCE_LOCK="${DATA_DIR}/instance.lock"
URL="http://127.0.0.1:${PORT}"

export ABI_DESKTOP_PORT="${PORT}"
export PYTHONPATH="${APPS_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

# Serialize parallel start attempts (e.g. multiple Cursor agents).
acquire_start_lock() {
  START_LOCK_FD="$(python3 - <<PY
import fcntl
import os
import sys

path = "${START_LOCK_FILE}"
os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    os.close(fd)
    sys.exit(2)
print(fd)
PY
)" || return $?
  export START_LOCK_FD
}

release_start_lock() {
  if [[ -n "${START_LOCK_FD:-}" ]]; then
    python3 -c "import fcntl, os; fd=int('${START_LOCK_FD}'); fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)" 2>/dev/null || true
    unset START_LOCK_FD
  fi
}

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

pid_alive() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

read_server_pid() {
  DATA_DIR="${DATA_DIR}" python3 - <<'PY' 2>/dev/null || true
import json
import os
import pathlib

path = pathlib.Path(os.environ["DATA_DIR"]) / "server.json"
try:
    print(json.loads(path.read_text()).get("pid", ""))
except Exception:
    pass
PY
}

is_healthy() {
  curl -sf "${URL}/api/health" >/dev/null 2>&1
}

is_abi_desktop_on_port() {
  DATA_DIR="${DATA_DIR}" PORT="${PORT}" python3 - <<'PY' 2>/dev/null
import json
import os
import sys
import urllib.error
import urllib.request

port = int(os.environ["PORT"])
url = f"http://127.0.0.1:{port}/api/health"
try:
    with urllib.request.urlopen(url, timeout=1.5) as resp:
        if resp.status != 200:
            sys.exit(1)
        payload = json.loads(resp.read().decode())
except Exception:
    sys.exit(1)
sys.exit(0 if payload.get("app") == "ABI Desktop" else 1)
PY
}

supervisor_pid() {
  if [[ -f "${SUPERVISOR_PID_FILE}" ]]; then
    cat "${SUPERVISOR_PID_FILE}"
  fi
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

  local old_pid
  old_pid="$(read_server_pid)"
  if [[ -n "${old_pid}" ]]; then
    kill_pids "${old_pid}"
  fi

  sleep 1
  rm -f "${INSTANCE_LOCK}"
  wait_for_port_free "${PORT}" 60 || {
    echo "error: port ${PORT} still busy after stop; set ABI_DESKTOP_PORT or quit the other process" >&2
    return 1
  }
}

# Detach supervisor in a new session so Cursor agent shell exit cannot SIGTERM it.
detach_supervisor() {
  REPO_ROOT="${REPO_ROOT}"   DEV_SH_SCRIPT="${BASH_SOURCE[0]}"   LOG_FILE="${LOG_FILE}"   PORT="${PORT}"   APPS_DIR="${APPS_DIR}"   python3 - <<'PY'
import os
import subprocess

repo = os.environ["REPO_ROOT"]
script = os.environ["DEV_SH_SCRIPT"]
log = os.environ["LOG_FILE"]
port = os.environ["PORT"]
apps = os.environ["APPS_DIR"]

env = os.environ.copy()
env["ABI_DESKTOP_PORT"] = port
env["ABI_DESKTOP_BROWSER"] = "1"
env["ABI_DESKTOP_RELOAD"] = "1"
py_path = env.get("PYTHONPATH", "")
env["PYTHONPATH"] = apps if not py_path else f"{apps}:{py_path}"

log_fh = open(log, "a", buffering=1)
proc = subprocess.Popen(
    ["bash", script, "_supervisor_loop"],
    start_new_session=True,
    stdin=subprocess.DEVNULL,
    stdout=log_fh,
    stderr=subprocess.STDOUT,
    cwd=repo,
    env=env,
    close_fds=True,
)
print(proc.pid)
PY
}

wait_for_health() {
  local attempts="${1:-60}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if is_healthy; then
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
  trap '' HUP TERM INT

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

print_ready() {
  local sup_pid="${1:-}"
  echo "ABI Desktop ready at ${URL}"
  if [[ -n "${sup_pid}" ]]; then
    echo "Supervisor PID ${sup_pid} (see ${SUPERVISOR_PID_FILE})"
  fi
  local worker_pid
  worker_pid="$(read_server_pid)"
  if [[ -n "${worker_pid}" ]]; then
    echo "Worker PID ${worker_pid} (see ${DATA_DIR}/server.json)"
  fi
  echo "Logs: ${LOG_FILE}"
}

show_status() {
  local sup_pid worker_pid healthy="no"
  sup_pid="$(supervisor_pid || true)"
  worker_pid="$(read_server_pid)"

  if is_healthy; then
    healthy="yes"
  fi

  echo "URL:      ${URL}"
  echo "Healthy:  ${healthy}"
  if [[ -n "${sup_pid}" ]] && pid_alive "${sup_pid}"; then
    echo "Supervisor PID: ${sup_pid} (running)"
  elif [[ -n "${sup_pid}" ]]; then
    echo "Supervisor PID: ${sup_pid} (stale)"
  else
    echo "Supervisor PID: (none)"
  fi
  if [[ -n "${worker_pid}" ]] && pid_alive "${worker_pid}"; then
    echo "Worker PID:     ${worker_pid} (running)"
  elif [[ -n "${worker_pid}" ]]; then
    echo "Worker PID:     ${worker_pid} (stale)"
  else
    echo "Worker PID:     (none)"
  fi
  if [[ "${healthy}" == "yes" ]]; then
    curl -sf "${URL}/api/health" | python3 -m json.tool 2>/dev/null || true
    return 0
  fi
  return 1
}

start_server() {
  mkdir -p "${DATA_DIR}"

  # Idempotent: never stop a healthy server (parallel agents must not kill each other).
  if is_healthy; then
    print_ready "$(supervisor_pid || true)"
    return 0
  fi

  acquire_start_lock || {
    echo "Another dev.sh start is in progress; waiting for health..." >&2
    if wait_for_health 90; then
      print_ready "$(supervisor_pid || true)"
      return 0
    fi
    echo "error: start lock held and server did not become healthy" >&2
    return 1
  }
  trap release_start_lock EXIT

  # Re-check after acquiring lock.
  if is_healthy; then
    print_ready "$(supervisor_pid || true)"
    return 0
  fi

  local sup_pid
  sup_pid="$(supervisor_pid || true)"
  if [[ -n "${sup_pid}" ]] && pid_alive "${sup_pid}"; then
    echo "Supervisor PID ${sup_pid} already running; waiting for health..." >&2
    if wait_for_health 90; then
      print_ready "${sup_pid}"
      return 0
    fi
    echo "error: supervisor running but server unhealthy; run dev.sh stop to reset" >&2
    return 1
  fi

  if ! port_is_free "${PORT}"; then
    if is_abi_desktop_on_port; then
      print_ready
      return 0
    fi
    local blocker
    blocker="$(lsof -ti ":${PORT}" 2>/dev/null | head -1 || true)"
    echo "error: port ${PORT} in use (PID ${blocker:-unknown}) by a non-ABI process" >&2
    echo "Run dev.sh stop to clear, or set ABI_DESKTOP_PORT to another port." >&2
    return 1
  fi

  rm -f "${INSTANCE_LOCK}"
  sup_pid="$(detach_supervisor)"
  echo "${sup_pid}" >"${SUPERVISOR_PID_FILE}"

  if wait_for_health 90; then
    print_ready "${sup_pid}"
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
  status)
    show_status
    ;;
  _supervisor_loop)
    _supervisor_loop
    ;;
  start | "")
    start_server
    ;;
  *)
    echo "usage: $0 [start|status|stop]" >&2
    exit 1
    ;;
esac
