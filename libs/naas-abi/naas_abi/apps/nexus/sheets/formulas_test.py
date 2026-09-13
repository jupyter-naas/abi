from naas_abi.apps.nexus.sheets.formulas import evaluate_workbook_formulas
from naas_abi.apps.nexus.sheets.model import SheetTab, SheetWorkbook


def test_evaluate_simple_arithmetic() -> None:
    wb = SheetWorkbook(
        title="Test",
        sheets=[
            SheetTab(
                name="Sheet1",
                rows=[
                    ["10", "20", "=A1+B1"],
                ],
            ),
        ],
    )
    out = evaluate_workbook_formulas(wb)
    assert out.sheets[0].rows[0][2] == 30.0


def test_evaluate_cell_reference() -> None:
    wb = SheetWorkbook(
        title="Test",
        sheets=[
            SheetTab(
                name="Sheet1",
                rows=[
                    ["5", "3", "=A1*B1"],
                ],
            ),
        ],
    )
    out = evaluate_workbook_formulas(wb)
    assert out.sheets[0].rows[0][2] == 15.0
