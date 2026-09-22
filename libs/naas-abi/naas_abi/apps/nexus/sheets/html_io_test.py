from pathlib import Path

from naas_abi.apps.nexus.sheets.html_io import parse_workbook_html
from naas_abi.apps.nexus.sheets.xlsx_export import workbook_to_xlsx_bytes


def test_parse_and_export_seed_template() -> None:
    root = Path(__file__).resolve().parents[1] / "assets" / "sheets" / "templates"
    html = (root / "grid-light-v1.html").read_text(encoding="utf-8")
    wb = parse_workbook_html(html)
    assert wb.title == "Untitled workbook"
    assert wb.sheets[0].name == "Sheet1"
    assert wb.sheets[0].rows == []
    xlsx = workbook_to_xlsx_bytes(wb)
    assert xlsx[:2] == b"PK"


def test_parse_and_export_monthly_pnl_seed() -> None:
    root = Path(__file__).resolve().parents[1] / "assets" / "sheets" / "templates"
    html = (root / "monthly-pnl-v1.html").read_text(encoding="utf-8")
    wb = parse_workbook_html(html)
    assert wb.title == "Monthly P&L"
    assert [tab.name for tab in wb.sheets] == ["Assumptions", "P&L", "Checks"]
    assert wb.sheets[1].rows[0][0] == "Line item (EUR '000)"
    assert wb.sheets[1].rows[7][1] == "=B4-B7"
    xlsx = workbook_to_xlsx_bytes(wb)
    assert xlsx[:2] == b"PK"


def test_dimensions_survive_duplicate_and_excel_export() -> None:
    import io

    import openpyxl
    from naas_abi.apps.nexus.sheets.html_io import serialize_workbook_html
    from naas_abi.apps.nexus.sheets.model import SheetTab, SheetWorkbook
    from naas_abi.apps.nexus.sheets.tab_mutations import duplicate_workbook_tab

    workbook = SheetWorkbook(
        sheets=[
            SheetTab(
                rows=[[4, 6, "=A1+B1"]], column_widths={0: 200}, row_heights={0: 60}
            )
        ]
    )
    restored = parse_workbook_html(serialize_workbook_html(workbook, template_html=""))
    duplicated = parse_workbook_html(
        duplicate_workbook_tab(serialize_workbook_html(restored, template_html=""), 0)[
            "html"
        ]
    )
    assert duplicated.sheets[1].column_widths == {0: 200}
    assert duplicated.sheets[1].row_heights == {0: 60}
    exported = openpyxl.load_workbook(io.BytesIO(workbook_to_xlsx_bytes(duplicated)))
    assert exported.worksheets[0]["C1"].value == "=A1+B1"
    assert abs(exported.worksheets[0].column_dimensions["A"].width - 195 / 7) < 0.001
    assert exported.worksheets[0].row_dimensions[1].height == 45
