#!/usr/bin/env bash
# Fail when a lock that runs (the repository's root uv.lock, which the release
# image and the compose `abi` service install, and the Nexus API's) holds a
# package with a published advisory that .github/advisories-allowlist.txt does
# not record. Needs uv 0.12 or later (`uv audit`) and network access to OSV.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
allowlist="$root/.github/advisories-allowlist.txt"

args=()
while read -r id mode _; do
  case "$id" in ""|\#*) continue ;; esac
  case "$mode" in
    ignore) args+=(--ignore "$id") ;;
    until-fixed) args+=(--ignore-until-fixed "$id") ;;
    *) echo "$allowlist: unknown mode '$mode' for $id" >&2; exit 2 ;;
  esac
done < "$allowlist"

status=0
for project in "$root" "$root/libs/naas-abi/naas_abi/apps/nexus/apps/api"; do
  echo "== ${project#"$root"/}: uv.lock"
  (cd "$project" && uv audit --frozen --preview-features audit-command "${args[@]}") || status=1
done
exit "$status"
