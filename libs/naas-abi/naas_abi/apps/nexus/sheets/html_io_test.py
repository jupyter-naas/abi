from pathlib import Path

from naas_abi.apps.nexus.sheets.html_io import parse_workbook_html
from naas_abi.apps.nexus.sheets.xlsx_export import workbook_to_xlsx_bytes


def test_parse_and_export_seed_template() -> None:
    root = Path(__file__).resolve().parents[1] / "assets" / "sheets" / "templates"
    html = (root / "grid-light-v1.html").read_text(encoding="utf-8")
    wb = parse_workbook_html(html)
    assert wb.title == "Sample budget"
    assert wb.sheets[0].rows[0][0] == "Category"
    xlsx = workbook_to_xlsx_bytes(wb)
    assert xlsx[:2] == b"PK"
