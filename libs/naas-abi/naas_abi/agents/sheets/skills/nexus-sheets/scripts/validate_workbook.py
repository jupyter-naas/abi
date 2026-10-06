"""Validate an offline Nexus workbook; do not modify its formula cells."""

import argparse
import json
from pathlib import Path

from naas_abi.apps.nexus.sheets.formulas import (
    evaluate_workbook_formulas,
    formula_errors,
)
from naas_abi.apps.nexus.sheets.html_io import parse_workbook_html


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    try:
        workbook = parse_workbook_html(args.workbook.read_text(encoding="utf-8"))
        errors = formula_errors(workbook)
        evaluated = evaluate_workbook_formulas(workbook)
        failing_checks = [
            {"sheet": tab.name, "row": i + 1}
            for tab in evaluated.sheets
            if tab.name.lower() in {"checks", "tie-out", "tieout"}
            for i, row in enumerate(tab.rows)
            if any(value == "BREAK" for value in row)
        ]
        result = {
            "ok": not errors and not failing_checks,
            "errors": errors,
            "failing_checks": failing_checks,
        }
    except (ValueError, OSError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
