from __future__ import annotations

import re
from typing import Any

from naas_abi.apps.nexus.sheets.model import SheetTab, SheetWorkbook

_CELL_REF_RE = re.compile(r"^([A-Za-z]+)(\d+)$")
_FORMULA_RE = re.compile(r"^\s*=")


def _col_index(col: str) -> int:
    n = 0
    for ch in col.upper():
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"invalid column {col!r}")
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def _cell_ref(ref: str) -> tuple[int, int]:
    m = _CELL_REF_RE.match(ref.strip())
    if not m:
        raise ValueError(f"invalid cell ref {ref!r}")
    return int(m.group(2)) - 1, _col_index(m.group(1))


def _cell_value(rows: list[list[Any]], row: int, col: int) -> float | str | None:
    if row < 0 or col < 0 or row >= len(rows):
        return None
    line = rows[row]
    if col >= len(line):
        return None
    val = line[col]
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip()
    if _FORMULA_RE.match(text):
        return text
    try:
        return float(text)
    except ValueError:
        return text


def _eval_expr(expr: str, rows: list[list[Any]]) -> Any:
    expr = expr.strip()
    if not expr:
        return None

    def repl(match: re.Match[str]) -> str:
        r, c = _cell_ref(match.group(0))
        v = _cell_value(rows, r, c)
        if v is None:
            return "0"
        if isinstance(v, str) and _FORMULA_RE.match(v):
            raise ValueError(f"circular ref at {match.group(0)}")
        if isinstance(v, str):
            try:
                return str(float(v))
            except ValueError:
                return repr(v)
        return str(float(v))

    safe = re.sub(r"[A-Za-z]+\d+", repl, expr)
    if not re.fullmatch(r"[\d\s+\-*/().]+", safe):
        raise ValueError(f"unsupported formula expression: {expr}")
    return eval(safe, {"__builtins__": {}}, {})  # noqa: S307


def evaluate_workbook_formulas(workbook: SheetWorkbook) -> SheetWorkbook:
    """Resolve ``=`` formulas in-place (simple arithmetic + A1 refs)."""
    out = workbook.model_copy(deep=True)
    for tab in out.sheets:
        rows = tab.rows
        for r_idx, row in enumerate(rows):
            for c_idx, cell in enumerate(row):
                if not isinstance(cell, str) or not _FORMULA_RE.match(cell):
                    continue
                try:
                    rows[r_idx][c_idx] = _eval_expr(cell[1:], rows)
                except Exception:
                    rows[r_idx][c_idx] = "#ERR"
    return out
