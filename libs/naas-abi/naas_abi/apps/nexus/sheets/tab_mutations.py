"""Workbook tab insert/delete/duplicate/reorder on the JSON sheet model."""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.sheets.html_io import parse_workbook_html, serialize_workbook_html
from naas_abi.apps.nexus.sheets.model import SheetTab, SheetWorkbook

OutlineItem = dict[str, Any]


def _outline(workbook: SheetWorkbook) -> list[OutlineItem]:
    return [
        {
            "index": index,
            "id": None,
            "eyebrow": "",
            "title": tab.name,
            "layout": "content",
        }
        for index, tab in enumerate(workbook.sheets)
    ]


def _ok(workbook: SheetWorkbook, html_template: str, active_index: int) -> dict[str, Any]:
    items = _outline(workbook)
    return {
        "html": serialize_workbook_html(workbook, template_html=html_template),
        "section_index": active_index,
        "section_count": len(workbook.sheets),
        "ids": [item["id"] for item in items],
        "slides": items,
    }


def list_workbook_tabs(html: str) -> list[OutlineItem]:
    workbook = parse_workbook_html(html)
    return _outline(workbook)


def insert_workbook_tab(
    html: str,
    *,
    after_index: int = -1,
    title: str = "",
    layout: str = "content",
) -> dict[str, Any]:
    del layout  # tabs have no slide layout; kept for API compatibility
    try:
        workbook = parse_workbook_html(html)
    except ValueError as exc:
        return {"error": str(exc)}
    name = (title or "").strip() or f"Sheet{len(workbook.sheets) + 1}"
    tab = SheetTab(name=name, rows=[["Column A", "Column B"], ["", ""]])
    insert_at = len(workbook.sheets) if after_index < 0 else min(after_index + 1, len(workbook.sheets))
    workbook.sheets.insert(insert_at, tab)
    return _ok(workbook, html, insert_at)


def delete_workbook_tab(html: str, index: int) -> dict[str, Any]:
    try:
        workbook = parse_workbook_html(html)
    except ValueError as exc:
        return {"error": str(exc)}
    if len(workbook.sheets) <= 1:
        return {"error": "Cannot delete the last sheet tab"}
    if index < 0 or index >= len(workbook.sheets):
        return {"error": f"tab index out of range: {index}"}
    workbook.sheets.pop(index)
    next_index = min(index, len(workbook.sheets) - 1)
    return _ok(workbook, html, next_index)


def duplicate_workbook_tab(html: str, index: int) -> dict[str, Any]:
    try:
        workbook = parse_workbook_html(html)
    except ValueError as exc:
        return {"error": str(exc)}
    if index < 0 or index >= len(workbook.sheets):
        return {"error": f"tab index out of range: {index}"}
    source = workbook.sheets[index]
    copy_name = f"{source.name} copy"
    copy_tab = SheetTab(name=copy_name, rows=[list(row) for row in source.rows])
    insert_at = index + 1
    workbook.sheets.insert(insert_at, copy_tab)
    return _ok(workbook, html, insert_at)


def reorder_workbook_tabs(
    html: str,
    *,
    from_index: int | None = None,
    to_index: int | None = None,
    order: list[int] | None = None,
) -> dict[str, Any]:
    try:
        workbook = parse_workbook_html(html)
    except ValueError as exc:
        return {"error": str(exc)}
    tabs = workbook.sheets
    n = len(tabs)
    if order is not None:
        if len(order) != n or sorted(order) != list(range(n)):
            return {"error": "order must be a permutation of tab indices"}
        workbook.sheets = [tabs[i] for i in order]
        return _ok(workbook, html, order.index(0) if 0 in order else 0)
    if from_index is None or to_index is None:
        return {"error": "from_index and to_index are required when order is omitted"}
    if from_index < 0 or from_index >= n or to_index < 0 or to_index >= n:
        return {"error": "from_index/to_index out of range"}
    if from_index == to_index:
        return _ok(workbook, html, from_index)
    moved = tabs.pop(from_index)
    tabs.insert(to_index, moved)
    workbook.sheets = tabs
    return _ok(workbook, html, to_index)
