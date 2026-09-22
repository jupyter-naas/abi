import pytest
from naas_abi.apps.nexus.sheets.cell_edits import update_cells
from naas_abi.apps.nexus.sheets.html_io import (
    parse_workbook_html,
    serialize_workbook_html,
)
from naas_abi.apps.nexus.sheets.model import SheetTab, SheetWorkbook


def test_targeted_edits_preserve_formulas_tabs_and_original():
    model = SheetWorkbook(
        sheets=[
            SheetTab(name="Inputs", rows=[[2, "=A1*2"]]),
            SheetTab(name="Other", rows=[["001"]]),
        ]
    )
    result = update_cells(model, "Inputs", {"A1": 5, "$C$3": "=SUM(A1:B1)"})
    assert result.sheets[0].rows == [[5, "=A1*2"], [], [None, None, "=SUM(A1:B1)"]]
    assert result.sheets[1] == model.sheets[1]
    assert model.sheets[0].rows == [[2, "=A1*2"]]


@pytest.mark.parametrize(
    "edits", [{"A0": 1}, {"A100000000": 1}, {"A1": {}}, {"A1": True}]
)
def test_rejects_invalid_edits_atomically(edits):
    model = SheetWorkbook()
    with pytest.raises(ValueError):
        update_cells(model, "Sheet1", edits)
    assert model.sheets[0].rows == []


def test_html_serialization_escapes_cell_data_and_regex_replacements():
    model = SheetWorkbook(
        sheets=[SheetTab(rows=[["</script><script>alert(1)</script>", r"C:\new\test"]])]
    )
    template = '<script type="application/vnd.nexus.sheet+json">{}</script>'
    html = serialize_workbook_html(model, template_html=template)
    assert "<script>alert" not in html
    assert parse_workbook_html(html) == model
