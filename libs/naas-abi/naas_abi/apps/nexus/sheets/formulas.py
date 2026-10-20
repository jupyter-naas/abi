"""Python formula engine for Nexus Sheets HTML workbooks.

Supports Excel-like arithmetic, A1 refs, cross-sheet refs, and a small
function set: SUM, IF, ABS, ROUND. Evaluation returns computed values;
the source workbook keeps formula strings for export.
"""

from __future__ import annotations

import ast
import math
import operator
import re
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from naas_abi.apps.nexus.sheets.model import SheetWorkbook

_FORMULA_RE = re.compile(r"^\s*=")
_CELL_REF_RE = re.compile(r"^([A-Za-z]+)(\d+)$")
# Sheet!A1 or 'P&L'!A1 (sheet names: letters, digits, spaces, & _ - %)
_SHEET_CELL_RE = re.compile(r"(?:'([^']+)'|([A-Za-z][A-Za-z0-9 _%&-]*))!([A-Za-z]+\d+)")
_SHEET_RANGE_RE = re.compile(
    r"(?:'([^']+)'|([A-Za-z][A-Za-z0-9 _%&-]*))!([A-Za-z]+\d+):([A-Za-z]+\d+)"
)
_LOCAL_RANGE_RE = re.compile(r"([A-Za-z]+\d+):([A-Za-z]+\d+)")
_LOCAL_CELL_RE = re.compile(r"(?<![A-Za-z0-9_'!])([A-Za-z]+\d+)\b")
_STRING_RE = re.compile(r'"([^"]*)"')
_COMPARE_RE = re.compile(
    r"(.+?)\s*(<=|>=|<>|!=|=|<|>)\s*(.+)$",
)


MAX_EVALUATION_WORK = 1_000_000
MAX_REFERENCE_DEPTH = 64


@dataclass
class _Evaluation:
    remaining: int = MAX_EVALUATION_WORK
    cache: dict[tuple[str, int, int], Any] = field(default_factory=dict)
    sheets: dict[str, list[list[Any]]] = field(default_factory=dict)

    def charge(self, amount: int = 1) -> None:
        self.remaining -= amount
        if self.remaining < 0:
            raise ValueError("Workbook calculation limit exceeded")


_evaluation: ContextVar[_Evaluation | None] = ContextVar(
    "sheets_evaluation", default=None
)


def _charge(amount: int = 1) -> None:
    context = _evaluation.get()
    if context is not None:
        context.charge(amount)


def _spreadsheet_round(value: float, digits: int) -> float:
    if not math.isfinite(value):
        raise ValueError("Non-finite formula result")
    if digits > 308:
        return value
    if digits < -308:
        return 0.0
    with localcontext() as ctx:
        ctx.prec = 640
        return float(
            Decimal(str(value)).quantize(
                Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP
            )
        )


def _col_index(col: str) -> int:
    n = 0
    for ch in col.upper():
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"invalid column {col!r}")
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def _a1(row: int, col: int) -> str:
    n = col + 1
    letters = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row + 1}"


def _cell_ref(ref: str) -> tuple[int, int]:
    m = _CELL_REF_RE.match(ref.strip())
    if not m:
        raise ValueError(f"invalid cell ref {ref!r}")
    return int(m.group(2)) - 1, _col_index(m.group(1))


def _sheet_map(workbook: SheetWorkbook) -> dict[str, list[list[Any]]]:
    return {tab.name: tab.rows for tab in workbook.sheets}


def _raw_cell(rows: list[list[Any]], row: int, col: int) -> Any:
    if row < 0 or col < 0 or row >= len(rows):
        return None
    line = rows[row]
    if col >= len(line):
        return None
    return line[col]


def _expand_range(start: str, end: str) -> list[tuple[int, int]]:
    r0, c0 = _cell_ref(start)
    r1, c1 = _cell_ref(end)
    if r0 > r1:
        r0, r1 = r1, r0
    if c0 > c1:
        c0, c1 = c1, c0
    if (r1 - r0 + 1) * (c1 - c0 + 1) > 100_000:
        raise ValueError("Formula range exceeds 100,000 cells")
    _charge((r1 - r0 + 1) * (c1 - c0 + 1))
    out: list[tuple[int, int]] = []
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            out.append((r, c))
    return out


def _to_number(val: Any) -> float:
    if val is None or val == "":
        return 0.0
    if isinstance(val, bool):
        return 1.0 if val else 0.0
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip()
    if not text or text in {"OK", "BREAK", "#ERR"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _resolve_cell(
    workbook: SheetWorkbook,
    sheet_name: str,
    row: int,
    col: int,
    visiting: set[tuple[str, int, int]],
) -> Any:
    _charge()
    key = (sheet_name, row, col)
    context = _evaluation.get()
    if context is not None and key in context.cache:
        cached = context.cache[key]
        if isinstance(cached, Exception):
            raise cached
        return cached
    if len(visiting) >= MAX_REFERENCE_DEPTH:
        raise ValueError("Formula reference depth limit exceeded")
    sheets = context.sheets if context is not None else _sheet_map(workbook)
    rows = sheets.get(sheet_name)
    if rows is None:
        raise ValueError(f"unknown sheet {sheet_name!r}")
    val = _raw_cell(rows, row, col)
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip()
    if len(text) > 4096:
        raise ValueError("Referenced cell exceeds calculation text limit")
    if _FORMULA_RE.match(text):
        key = (sheet_name, row, col)
        if key in visiting:
            raise ValueError(f"circular ref at {sheet_name}!{_a1(row, col)}")
        try:
            result = _eval_expr(text[1:], workbook, sheet_name, visiting | {key})
        except (
            ValueError,
            ArithmeticError,
            SyntaxError,
            RecursionError,
            TypeError,
        ) as exc:
            if context is not None:
                context.cache[key] = exc
            raise
        if context is not None:
            context.cache[key] = result
        return result
    try:
        return float(text)
    except ValueError:
        return text


def _num_lit(value: float) -> str:
    """Format a number so later arithmetic parsing accepts it (no bare ``e`` issues)."""
    if not math.isfinite(value):
        raise ValueError("Non-finite formula result")
    # Decimal expansion preserves the float's round-trip representation without
    # introducing exponent tokens that could be mistaken for cell references.
    return format(Decimal(repr(float(value))), "f")


def _find_matching_paren(s: str, open_idx: int) -> int:
    depth = 0
    in_str = False
    for i in range(open_idx, len(s)):
        ch = s[i]
        if ch == '"' and (i == 0 or s[i - 1] != "\\"):
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unbalanced parentheses in {s!r}")


def _split_args(arg_str: str) -> list[str]:
    args: list[str] = []
    depth = 0
    in_str = False
    start = 0
    for i, ch in enumerate(arg_str):
        if ch == '"' and (i == 0 or arg_str[i - 1] != "\\"):
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            args.append(arg_str[start:i].strip())
            start = i + 1
    args.append(arg_str[start:].strip())
    return [a for a in args if a != ""]


def _eval_compare(left: Any, op: str, right: Any) -> bool:
    if op in {"=", "=="}:
        if isinstance(left, str) or isinstance(right, str):
            return str(left) == str(right)
        return _to_number(left) == _to_number(right)
    if op in {"<>", "!="}:
        if isinstance(left, str) or isinstance(right, str):
            return str(left) != str(right)
        return _to_number(left) != _to_number(right)
    ln, rn = _to_number(left), _to_number(right)
    if op == "<":
        return ln < rn
    if op == ">":
        return ln > rn
    if op == "<=":
        return ln <= rn
    if op == ">=":
        return ln >= rn
    raise ValueError(f"unsupported compare op {op!r}")


def _sum_cells(
    workbook: SheetWorkbook,
    sheet_name: str,
    cells: list[tuple[int, int]],
    visiting: set[tuple[str, int, int]],
) -> float:
    total = 0.0
    for r, c in cells:
        total += _to_number(_resolve_cell(workbook, sheet_name, r, c, visiting))
    return total


def _rewrite_functions(
    expr: str,
    workbook: SheetWorkbook,
    sheet_name: str,
    visiting: set[tuple[str, int, int]],
) -> str:
    """Replace SUM/IF/ABS/ROUND calls with numeric or quoted literals."""
    out = expr
    # Process innermost function calls repeatedly.
    func_re = re.compile(r"\b(SUM|IF|ABS|ROUND)\s*\(", re.IGNORECASE)
    while True:
        m = func_re.search(out)
        if not m:
            break
        name = m.group(1).upper()
        open_idx = m.end() - 1
        close_idx = _find_matching_paren(out, open_idx)
        inner = out[open_idx + 1 : close_idx]
        args = _split_args(inner)
        if name == "SUM":
            total = 0.0
            for arg in args:
                arg = arg.strip()
                sm = _SHEET_RANGE_RE.fullmatch(arg)
                if sm:
                    sn = sm.group(1) or sm.group(2)
                    total += _sum_cells(
                        workbook,
                        sn,
                        _expand_range(sm.group(3), sm.group(4)),
                        visiting,
                    )
                    continue
                lm = _LOCAL_RANGE_RE.fullmatch(arg)
                if lm:
                    total += _sum_cells(
                        workbook,
                        sheet_name,
                        _expand_range(lm.group(1), lm.group(2)),
                        visiting,
                    )
                    continue
                total += _to_number(_eval_expr(arg, workbook, sheet_name, visiting))
            replacement = _num_lit(float(total))
        elif name == "ABS":
            if len(args) != 1:
                raise ValueError(f"ABS expects 1 arg, got {len(args)}")
            replacement = _num_lit(
                abs(_to_number(_eval_expr(args[0], workbook, sheet_name, visiting)))
            )
        elif name == "ROUND":
            if len(args) not in (1, 2):
                raise ValueError(f"ROUND expects 1 or 2 args, got {len(args)}")
            value = _to_number(_eval_expr(args[0], workbook, sheet_name, visiting))
            digits = (
                int(_to_number(_eval_expr(args[1], workbook, sheet_name, visiting)))
                if len(args) == 2
                else 0
            )
            replacement = _num_lit(_spreadsheet_round(value, digits))
        elif name == "IF":
            if len(args) != 3:
                raise ValueError(f"IF expects 3 args, got {len(args)}")
            cond_raw = args[0].strip()
            cm = _COMPARE_RE.match(cond_raw)
            if cm:
                left = _eval_expr(cm.group(1), workbook, sheet_name, visiting)
                right = _eval_expr(cm.group(3), workbook, sheet_name, visiting)
                ok = _eval_compare(left, cm.group(2), right)
            else:
                ok = bool(
                    _to_number(_eval_expr(cond_raw, workbook, sheet_name, visiting))
                )
            chosen = args[1] if ok else args[2]
            result = _eval_expr(chosen, workbook, sheet_name, visiting)
            if isinstance(result, str):
                replacement = '"' + result.replace('"', "") + '"'
            elif result is None:
                replacement = "0"
            else:
                replacement = _num_lit(float(result))
        else:
            raise ValueError(f"unsupported function {name}")
        out = out[: m.start()] + replacement + out[close_idx + 1 :]
    return out


def _arithmetic(expression: str) -> float:
    """Evaluate only numeric arithmetic nodes; never execute formula text."""
    tree = ast.parse(expression, mode="eval")
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    def visit(node: ast.AST) -> float:
        _charge()
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return float(operations[type(node.op)](visit(node.left), visit(node.right)))
        raise ValueError("Unsupported arithmetic expression")

    result = visit(tree.body)
    if not math.isfinite(result):
        raise ValueError("Non-finite formula result")
    return result


def _eval_expr(
    expr: str,
    workbook: SheetWorkbook,
    sheet_name: str,
    visiting: set[tuple[str, int, int]],
) -> Any:
    _charge(len(expr) + 1)
    expr = expr.strip()
    if len(expr) > 4096:
        raise ValueError("Formula exceeds 4,096 characters")
    if not expr:
        return None

    # String literal alone
    sm = _STRING_RE.fullmatch(expr)
    if sm:
        return sm.group(1)

    expr = _rewrite_functions(expr, workbook, sheet_name, visiting)

    # Cross-sheet cells
    def sheet_cell_repl(match: re.Match[str]) -> str:
        sn = match.group(1) or match.group(2)
        r, c = _cell_ref(match.group(3))
        v = _resolve_cell(workbook, sn, r, c, visiting)
        if isinstance(v, str):
            return '"' + v.replace('"', "") + '"'
        return _num_lit(_to_number(v))

    expr = _SHEET_CELL_RE.sub(sheet_cell_repl, expr)

    # Local cells
    def local_cell_repl(match: re.Match[str]) -> str:
        r, c = _cell_ref(match.group(1))
        v = _resolve_cell(workbook, sheet_name, r, c, visiting)
        if isinstance(v, str):
            return '"' + v.replace('"', "") + '"'
        return _num_lit(_to_number(v))

    expr = _LOCAL_CELL_RE.sub(local_cell_repl, expr)

    # Pure string after rewrites
    sm = _STRING_RE.fullmatch(expr.strip())
    if sm:
        return sm.group(1)

    safe = expr.strip()
    if re.fullmatch(r'"[^"]*"', safe):
        return safe[1:-1]
    if not re.fullmatch(r"[\d\s+\-*/().]+", safe):
        raise ValueError(f"unsupported formula expression: {expr}")
    if "**" in safe or "//" in safe:
        raise ValueError("Unsupported arithmetic operator")
    return _arithmetic(safe)


def calculate_workbook(
    workbook: SheetWorkbook,
) -> tuple[SheetWorkbook, list[dict[str, str]]]:
    """One bounded, memoized calculation; preserve raw formulas in the input."""
    if (
        len(workbook.sheets) > 256
        or sum(len(row) for tab in workbook.sheets for row in tab.rows) > 100_000
    ):
        raise ValueError("Workbook calculation size limit exceeded")
    out = workbook.model_copy(deep=True)
    errors: list[dict[str, str]] = []
    context = _Evaluation()
    context.sheets = _sheet_map(workbook)
    token = _evaluation.set(context)
    try:
        for tab in out.sheets:
            for r_idx, row in enumerate(tab.rows):
                for c_idx, cell in enumerate(row):
                    if not isinstance(cell, str) or not _FORMULA_RE.match(cell):
                        continue
                    try:
                        row[c_idx] = _resolve_cell(
                            workbook, tab.name, r_idx, c_idx, set()
                        )
                    except (
                        ValueError,
                        ArithmeticError,
                        SyntaxError,
                        RecursionError,
                        TypeError,
                    ) as exc:
                        row[c_idx] = "#ERR"
                        errors.append(
                            {
                                "sheet": tab.name,
                                "cell": _a1(r_idx, c_idx),
                                "formula": cell,
                                "error": str(exc),
                            }
                        )
    finally:
        _evaluation.reset(token)
    return out, errors


def evaluate_workbook_formulas(workbook: SheetWorkbook) -> SheetWorkbook:
    return calculate_workbook(workbook)[0]


def formula_errors(workbook: SheetWorkbook) -> list[dict[str, str]]:
    return calculate_workbook(workbook)[1]
