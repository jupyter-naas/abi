from naas_abi.apps.nexus.sheets.tab_mutations import (
    delete_workbook_tab,
    duplicate_workbook_tab,
    insert_workbook_tab,
    list_workbook_tabs,
    reorder_workbook_tabs,
)

SAMPLE = """<!doctype html><html><head>
<script type="application/vnd.nexus.sheet+json">
{"title":"T","sheets":[{"name":"Sheet1","rows":[["A"]]},{"name":"Sheet2","rows":[["B"]]}]}
</script></head><body></body></html>"""


def test_list_tabs() -> None:
    tabs = list_workbook_tabs(SAMPLE)
    assert len(tabs) == 2
    assert tabs[0]["title"] == "Sheet1"


def test_insert_tab() -> None:
    out = insert_workbook_tab(SAMPLE, after_index=0, title="Mid")
    assert "error" not in out
    assert out["section_count"] == 3
    assert out["section_index"] == 1
    assert any(s["title"] == "Mid" for s in out["slides"])


def test_delete_tab() -> None:
    out = delete_workbook_tab(SAMPLE, 1)
    assert out["section_count"] == 1
    err = delete_workbook_tab(out["html"], 0)
    assert err.get("error")


def test_duplicate_and_reorder() -> None:
    dup = duplicate_workbook_tab(SAMPLE, 0)
    assert dup["section_count"] == 3
    reordered = reorder_workbook_tabs(dup["html"], from_index=2, to_index=0)
    assert reordered["section_index"] == 0
    assert reordered["section_count"] == 3
