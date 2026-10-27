#!/usr/bin/env bash
# Package size guard: build every package the Release job publishes to PyPI and
# fail when a wheel or an sdist is over the per-file budget. PyPI caps a whole
# project at 10 GiB, so a few MB per file adds up over hundreds of releases.
# CI runs it on every PR into main (the `package-size` job); run it locally with:
#
#   make check-package-size
#   PACKAGE_SIZE_BUDGET_MIB=1 scripts/check_package_size.sh   # lower budget, to see it fail
#
# Needs uv. Builds go to a temp dir that is removed afterwards.
#
# Environment:
#   PACKAGE_SIZE_BUDGET_MIB  per-file budget in MiB (default 10)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUDGET_MIB="${PACKAGE_SIZE_BUDGET_MIB:-10}"
BUDGET_BYTES=$((BUDGET_MIB * 1024 * 1024))

# The packages the Release job publishes (.github/workflows/release.yml).
PACKAGES=(
  naas-abi-proto
  naas-abi-sdk
  naas-abi-core
  naas-abi-marketplace
  naas-abi
  naas-abi-cli
)

OUT_DIR="$(mktemp -d)"
trap 'rm -rf "$OUT_DIR"' EXIT

over=()
printf '%-52s %12s %12s  %s\n' "FILE" "SIZE (B)" "BUDGET (B)" "STATUS"
for package in "${PACKAGES[@]}"; do
  pkg_out="$OUT_DIR/$package"
  if ! uv build --project "$REPO/libs/$package" --out-dir "$pkg_out" "$REPO/libs/$package" >"$OUT_DIR/build.log" 2>&1; then
    cat "$OUT_DIR/build.log" >&2
    echo "Build of $package failed" >&2
    exit 1
  fi
  for file in "$pkg_out"/*.whl "$pkg_out"/*.tar.gz; do
    [ -e "$file" ] || continue
    size="$(stat -c %s "$file" 2>/dev/null || stat -f %z "$file")"
    if [ "$size" -gt "$BUDGET_BYTES" ]; then
      status="OVER BUDGET"
      over+=("$(basename "$file") ($size bytes)")
    else
      status="ok"
    fi
    printf '%-52s %12s %12s  %s\n' "$(basename "$file")" "$size" "$BUDGET_BYTES" "$status"
  done
done

if [ "${#over[@]}" -gt 0 ]; then
  echo "" >&2
  echo "Package size check failed: over the ${BUDGET_MIB} MiB budget:" >&2
  printf '  %s\n' "${over[@]}" >&2
  exit 1
fi
echo ""
echo "Package size check passed: every file is within ${BUDGET_MIB} MiB."
