"""Export a Nexus Sheets HTML workbook to XLSX.

Usage::

    uv run python -m naas_abi.apps.nexus.sheets.cli workbook.html -o out.xlsx
"""

from __future__ import annotations

import argparse
from pathlib import Path

from naas_abi.apps.nexus.sheets.html_io import grid_from_table_html, parse_workbook_html
from naas_abi.apps.nexus.sheets.xlsx_export import workbook_to_xlsx_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Nexus Sheets HTML to XLSX")
    parser.add_argument("html", type=Path, help="Path to workbook.html")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output .xlsx path")
    args = parser.parse_args()
    text = args.html.read_text(encoding="utf-8")
    try:
        workbook = parse_workbook_html(text)
    except ValueError:
        workbook = grid_from_table_html(text)
        if workbook is None:
            raise SystemExit("Could not parse sheet JSON or sheet-grid table") from None
    args.output.write_bytes(workbook_to_xlsx_bytes(workbook))


if __name__ == "__main__":
    main()
