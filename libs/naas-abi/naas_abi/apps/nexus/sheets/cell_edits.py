"""Targeted workbook edits shared by agent tools and offline automation."""

from __future__ import annotations

import re
from typing import Any

from naas_abi.apps.nexus.sheets.model import SheetWorkbook


def update_cells(
    workbook: SheetWorkbook, sheet_name: str, edits: dict[str, Any]
) -> SheetWorkbook:
    """Return an edited copy, preserving all cells outside explicit A1 addresses."""
    if len(edits) > 10_000:
        raise ValueError("Update at most 10,000 cells per call")
    result = workbook.model_copy(deep=True)
    tab = next((sheet for sheet in result.sheets if sheet.name == sheet_name), None)
    if tab is None:
        raise ValueError(f"Unknown sheet: {sheet_name}")
    for address, value in edits.items():
        match = re.fullmatch(r"\$?([A-Za-z]+)\$?([1-9]\d*)", address)
        if not match:
            raise ValueError(f"Invalid cell address: {address}")
        col = 0
        for letter in match[1].upper():
            col = col * 26 + ord(letter) - ord("A") + 1
        row = int(match[2])
        # The current dense row model is intentionally bounded for targeted edits.
        if row > 10_000 or col > 1_000 or row * col > 100_000:
            raise ValueError("Cell address exceeds the editable workbook range")
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (str, int, float))
        ):
            raise ValueError(
                f"Invalid value at {address}: use text, a number, a formula, or null"
            )
        while len(tab.rows) < row:
            tab.rows.append([])
        while len(tab.rows[row - 1]) < col:
            tab.rows[row - 1].append(None)
        tab.rows[row - 1][col - 1] = value
    return result
