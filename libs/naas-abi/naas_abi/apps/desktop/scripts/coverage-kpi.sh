#!/usr/bin/env bash
# Emit a single-line coverage KPI for CI dashboards.
# Reads artifacts written by scripts/test.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COVERAGE_JSON="${DESKTOP_DIR}/.coverage-report.json"
JUNIT_XML="${DESKTOP_DIR}/.test-results.xml"

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

cd "${REPO_ROOT}"

uv run python - "${COVERAGE_JSON}" "${JUNIT_XML}" <<'PY'
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

coverage_path = Path(sys.argv[1])
junit_path = Path(sys.argv[2])

if not coverage_path.is_file():
    raise SystemExit(f"missing coverage report: {coverage_path}")
if not junit_path.is_file():
    raise SystemExit(f"missing junit report: {junit_path}")

cov_pct = json.loads(coverage_path.read_text())["totals"]["percent_covered"]
root = ET.parse(junit_path).getroot()
suite = root if root.tag == "testsuite" else root.find("testsuite")
if suite is None:
    raise SystemExit("junit xml missing testsuite element")

tests = int(suite.get("tests", 0))
failures = int(suite.get("failures", 0))
errors = int(suite.get("errors", 0))
passed = tests - failures - errors
failed = failures + errors

print(f"desktop_coverage={cov_pct:.1f} pass={passed} fail={failed}")
PY
