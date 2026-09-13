from naas_abi.agents.tools.sheets_workbook_storage import (
    branch_name,
    workbook_path,
)


def test_workbook_paths_are_namespaced_under_sheets() -> None:
    assert workbook_path("budget-q1", "ws-abc") == "sheets/ws-abc/budget-q1/workbook.html"
    assert branch_name("budget-q1", "ws-abc") == "sheets/ws-abc/budget-q1"
