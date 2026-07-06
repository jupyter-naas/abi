#!/usr/bin/env bash
#
# Fuseki / TDB2 backup + compaction helper (rendered into a deployment's
# .deploy/docker/fuseki/backup.sh by `abi deploy local`).
#
# Why this exists
# ---------------
# TDB2 corruption after an unclean shutdown (OOM-kill, disk-full mid-write) is
# the failure mode behind the intermittent/boot-time HTTP 500s on this store.
# Two server-side operations make that recoverable and less likely:
#
#   * backup  -> writes a consistent N-Quads dump of the dataset to the Fuseki
#                data volume ($FUSEKI_BASE/backups/). If the live TDB2 files are
#                ever wedged, you reload from the most recent good dump instead
#                of losing the graph.
#   * compact -> rewrites the TDB2 database into a fresh, defragmented copy and
#                (with deleteOld=true) drops the old generation. Reclaims the
#                disk that append-only TDB2 growth eats, and a freshly written
#                copy is far less prone to the states that precede corruption.
#
# Both run through Fuseki's admin HTTP API — no container exec required.
#
# Usage (run from the deployment root, where the .env lives)
# ----------------------------------------------------------
#   set -a; . ./.env; set +a
#   bash .deploy/docker/fuseki/backup.sh            # backup only
#   bash .deploy/docker/fuseki/backup.sh --compact  # backup + compact
#
# Environment
# -----------
#   FUSEKI_ADMIN_PASSWORD  (required) admin password (from the deployment .env)
#   FUSEKI_URL             base URL, default http://localhost:3030
#   FUSEKI_DATASET         dataset name, default ds
#   FUSEKI_ADMIN_USER      admin user, default admin
#
# Scheduling
# ----------
# Run this on a schedule (nightly is sensible). Since the stack already runs
# Dagster, a Dagster schedule that shells out here is the most native option; a
# host cron entry works too:
#   0 3 * * *  cd /path/to/deployment && set -a && . ./.env && set +a && \
#              bash .deploy/docker/fuseki/backup.sh --compact
#
set -euo pipefail

FUSEKI_URL="${FUSEKI_URL:-http://localhost:3030}"
FUSEKI_DATASET="${FUSEKI_DATASET:-ds}"
FUSEKI_ADMIN_USER="${FUSEKI_ADMIN_USER:-admin}"
DO_COMPACT=0

for arg in "$@"; do
  case "$arg" in
    --compact) DO_COMPACT=1 ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [[ -z "${FUSEKI_ADMIN_PASSWORD:-}" ]]; then
  echo "ERROR: FUSEKI_ADMIN_PASSWORD is not set (source the deployment .env first)." >&2
  exit 1
fi

AUTH=(-u "${FUSEKI_ADMIN_USER}:${FUSEKI_ADMIN_PASSWORD}")
BASE="${FUSEKI_URL%/}"

# Trigger an async admin task and echo the task id it returns.
_trigger() {
  local path="$1"
  curl -fsS -X POST "${AUTH[@]}" "${BASE}${path}" \
    | grep -o '"taskId"[^,}]*' | grep -o '[0-9]\+' | head -n1
}

# Poll /$/tasks/<id> until the task reports it finished; fail on error.
_wait_for_task() {
  local task_id="$1" label="$2"
  [[ -z "$task_id" ]] && { echo "  (no task id returned for ${label}; assuming synchronous completion)"; return 0; }
  echo "  ${label}: task ${task_id} running…"
  for _ in $(seq 1 120); do
    local body
    body="$(curl -fsS "${AUTH[@]}" "${BASE}/\$/tasks/${task_id}")" || true
    if echo "$body" | grep -q '"finished"'; then
      if echo "$body" | grep -qi '"success"[[:space:]]*:[[:space:]]*false'; then
        echo "  ${label}: FAILED — ${body}" >&2
        return 1
      fi
      echo "  ${label}: done."
      return 0
    fi
    sleep 5
  done
  echo "  ${label}: timed out waiting for completion" >&2
  return 1
}

echo "==> Backing up dataset '${FUSEKI_DATASET}' at ${BASE}"
BACKUP_TASK="$(_trigger "/\$/backup/${FUSEKI_DATASET}")"
_wait_for_task "$BACKUP_TASK" "backup"
echo "    Backup written to the Fuseki data volume under \$FUSEKI_BASE/backups/"

if [[ "$DO_COMPACT" -eq 1 ]]; then
  echo "==> Compacting dataset '${FUSEKI_DATASET}' (deleteOld=true)"
  COMPACT_TASK="$(_trigger "/\$/compact/${FUSEKI_DATASET}?deleteOld=true")"
  _wait_for_task "$COMPACT_TASK" "compact"
fi

echo "==> Done."
