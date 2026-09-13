from __future__ import annotations

import io

from naas_abi.apps.nexus.sheets.model import SheetWorkbook


def workbook_to_xlsx_bytes(workbook: SheetWorkbook) -> bytes:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("XLSX export requires openpyxl") from exc

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for tab in workbook.sheets or [SheetWorkbook().sheets[0]]:
        ws = wb.create_sheet(title=(tab.name or "Sheet1")[:31])
        for r_idx, row in enumerate(tab.rows, start=1):
            for c_idx, value in enumerate(row, start=1):
                ws.cell(row=r_idx, column=c_idx, value=value)
    if not wb.sheetnames:
        wb.create_sheet("Sheet1")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
