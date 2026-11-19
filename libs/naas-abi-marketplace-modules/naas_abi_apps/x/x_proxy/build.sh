#!/usr/bin/env bash
# Build the X Proxy dashboard's web export (Next.js static export in web/out/).
#
# Phases:
#   --web      pnpm build in web/ (skipped with a warning if pnpm is missing)
#   --check    say where the X module looks for the export (web/out/,
#              X_APP_WEB_EXPORT_DIR, /opt/x-app-web/out)
#
# Publishing is the remote X module's `build_app` job (hourly, or run it from
# System -> Jobs): it rebuilds the JSON snapshots from the dataset and uploads
# the export it finds to object storage, where the module's app serves it.
# The export is built with a placeholder basePath (web/next.config.js) that the
# module's app rewrites per request, so one build serves every session.
#
# Usage (from any cwd):
#   ./build.sh --web
#   ./build.sh --check

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --web)
      PHASE=web
      shift
      ;;
    --check)
      PHASE=check
      shift
      ;;
    -h|--help)
      sed -n '2,17p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$PHASE" ]]; then
  echo "Usage: $0 --web | --check" >&2
  exit 2
fi

if [[ "$PHASE" == "check" ]]; then
  exec uv run python -m naas_abi_apps.x.x_proxy.build
fi

if [[ ! -f "$APP_DIR/web/package.json" ]]; then
  echo "No web/package.json; skipping X Proxy web build"
  exit 0
fi
if ! command -v pnpm >/dev/null 2>&1; then
  echo "WARN: pnpm not found; skipping X Proxy web build (an image may bake the export)" >&2
  exit 0
fi
cd "$APP_DIR/web"
if [[ -f pnpm-lock.yaml ]]; then
  pnpm install --frozen-lockfile || pnpm install
else
  pnpm install
fi
pnpm build
