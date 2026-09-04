#!/usr/bin/env bash
# Build hook for the X Proxy dashboard (declared in manifest.json "rebuild").
#
# Phases:
#   --web      pnpm build in web/ (skipped with a warning if pnpm is missing)
#   --publish  upload web/out/ only (--web-only). Snapshot rebuild is owned by
#              the x_build_pipeline_hub Dagster schedule, like other hub shells.
#
# Usage (from repo root or any cwd):
#   ./build.sh --web
#   ./build.sh --publish [--config config.local.yaml]

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REBUILD_NEXUS_APPS_ROOT:-$(cd "$APP_DIR/../../../../../../../.." && pwd)}"
PHASE=""
CONFIG="${ABI_CONFIG:-config.local.yaml}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --web)
      PHASE=web
      shift
      ;;
    --publish)
      PHASE=publish
      shift
      ;;
    --config)
      CONFIG="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$PHASE" ]]; then
  echo "Usage: $0 --web | --publish [--config PATH]" >&2
  exit 2
fi

if [[ "$PHASE" == "web" ]]; then
  if [[ ! -f "$APP_DIR/web/package.json" ]]; then
    echo "No web/package.json; skipping X Proxy web build"
    exit 0
  fi
  if ! command -v pnpm >/dev/null 2>&1; then
    echo "WARN: pnpm not found; skipping X Proxy web build (Docker bake may supply export)" >&2
    exit 0
  fi
  (
    cd "$APP_DIR/web"
    if [[ -f pnpm-lock.yaml ]]; then
      pnpm install --frozen-lockfile || pnpm install
    else
      pnpm install
    fi
    pnpm build
  )
  exit 0
fi

cd "$REPO_ROOT"
"$REPO_ROOT/scripts/ensure_writable_egg_info.sh" "$REPO_ROOT"
"$REPO_ROOT/scripts/ensure_writable_storage_events.sh" "$REPO_ROOT"

_publish_host() {
  uv run python -m naas_abi_marketplace.applications.x.apps.x_proxy.build \
    --config "$CONFIG" --web-only
}

_publish_docker() {
  docker compose exec -T dagster \
    uv run python -m naas_abi_marketplace.applications.x.apps.x_proxy.build \
    --config "/app/$CONFIG" --web-only
}

if [[ -f "$APP_DIR/web/out/index.html" ]]; then
  _publish_host
elif [[ -f /.dockerenv ]]; then
  _publish_host
elif command -v docker >/dev/null 2>&1 \
  && docker compose ps --status running dagster 2>/dev/null | grep -q dagster; then
  # Host publish cannot see /opt/x-app-web/out; the running image can.
  _publish_docker
else
  _publish_host
fi
