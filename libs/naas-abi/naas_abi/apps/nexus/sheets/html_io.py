from __future__ import annotations

import json
import re

from naas_abi.apps.nexus.sheets.model import SheetTab, SheetWorkbook

_SHEET_JSON_TYPE = "application/vnd.nexus.sheet+json"
_JSON_SCRIPT_RE = re.compile(
    r'<script\s+[^>]*type=["\']'
    + re.escape(_SHEET_JSON_TYPE)
    + r'["\'][^>]*>(?P<body>.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def parse_workbook_html(html: str) -> SheetWorkbook:
    match = _JSON_SCRIPT_RE.search(html or "")
    if not match:
        raise ValueError("Missing nexus sheet JSON block in HTML")
    raw = match.group("body").strip()
    data = json.loads(raw)
    return SheetWorkbook.model_validate(data)


def serialize_workbook_html(workbook: SheetWorkbook, *, template_html: str) -> str:
    payload = json.dumps(workbook.model_dump(), indent=2)
    block = f'<script type="{_SHEET_JSON_TYPE}">\n{payload}\n</script>'
    if _JSON_SCRIPT_RE.search(template_html):
        return _JSON_SCRIPT_RE.sub(block, template_html, count=1)
    if "</head>" in template_html:
        return template_html.replace("</head>", f"{block}\n</head>", 1)
    return template_html + "\n" + block


def grid_from_table_html(html: str) -> SheetWorkbook | None:
    """Best-effort parse from ``table.sheet-grid`` when JSON is absent."""
    table_match = re.search(
        r'<table[^>]*class=["\'][^"\']*sheet-grid[^"\']*["\'][^>]*>(?P<body>.*?)</table>',
        html or "",
        re.DOTALL | re.IGNORECASE,
    )
    if not table_match:
        return None
    rows: list[list[str | None]] = []
    for tr in re.finditer(
        r"<tr[^>]*>(?P<cells>.*?)</tr>",
        table_match.group("body"),
        re.DOTALL | re.IGNORECASE,
    ):
        cells: list[str | None] = []
        for td in re.finditer(
            r"<t[dh][^>]*>(?P<cell>.*?)</t[dh]>",
            tr.group("cells"),
            re.DOTALL | re.IGNORECASE,
        ):
            text = re.sub(r"<[^>]+>", "", td.group("cell"))
            text = text.replace("&nbsp;", " ").strip()
            cells.append(text or None)
        if cells:
            rows.append(cells)
    if not rows:
        return None
    return SheetWorkbook(title="Workbook", sheets=[SheetTab(name="Sheet1", rows=rows)])
