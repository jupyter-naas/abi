"""EventBridge-style dict filters translated to SQLite JSON1 SQL.

A filter is a dict whose keys are dotted paths into the stored event JSON
and whose values are one of:

- a scalar (equals)
- a list (IN)
- an operator dict, e.g. ``{"gte": 5}``, ``{"prefix": "user-"}``,
  ``{"in": [...]}``, ``{"exists": False}``, ``{"ne": "x"}``

Multiple keys are AND-joined. The whole thing is a small declarative
subset of EventBridge's content-filter language.

Path safety: keys are restricted to ``[A-Za-z0-9_.\\-]+`` so they cannot
break out of the SQL string. Values are always parameterized.
"""

from __future__ import annotations

import re
from typing import Any

_PATH_RE = re.compile(r"^[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*$")

_NUMERIC_OPS = {"gt", "gte", "lt", "lte"}


class FilterError(ValueError):
    """Raised when a filter dict is malformed."""


def _path_to_json_path(key: str) -> str:
    if not _PATH_RE.match(key):
        raise FilterError(
            f"Invalid filter path {key!r}: must match {_PATH_RE.pattern}"
        )
    return "$." + key


def _extractor(column: str, key: str) -> str:
    """SQLite JSON1 extractor for a dotted path key."""
    return f"{column} ->> '{_path_to_json_path(key)}'"


def build_where(filter: dict[str, Any], column: str = "payload") -> tuple[str, list]:
    """Translate a filter dict to (SQL WHERE fragment, params list).

    The SQL fragment does NOT include the leading "WHERE" or "AND". The
    caller composes it into a larger query.

    Returns ("", []) if the filter is empty.
    """
    if not filter:
        return "", []

    clauses: list[str] = []
    params: list[Any] = []

    for key, value in filter.items():
        ext = _extractor(column, key)

        if isinstance(value, dict):
            # Operator dict: one or more {op: value} pairs, AND-joined.
            for op, opval in value.items():
                _emit_op(ext, op, opval, clauses, params)

        elif isinstance(value, list):
            if not value:
                # `key IN ()` is always false — mark as never-matches.
                clauses.append("0 = 1")
            else:
                placeholders = ",".join("?" for _ in value)
                clauses.append(f"{ext} IN ({placeholders})")
                params.extend(str(v) for v in value)

        elif value is None:
            clauses.append(f"{ext} IS NULL")

        else:
            clauses.append(f"{ext} = ?")
            params.append(_param(value))

    return " AND ".join(clauses), params


def _emit_op(ext: str, op: str, val: Any, clauses: list[str], params: list[Any]) -> None:
    if op == "gte":
        clauses.append(f"CAST({ext} AS REAL) >= ?")
        params.append(val)
    elif op == "gt":
        clauses.append(f"CAST({ext} AS REAL) > ?")
        params.append(val)
    elif op == "lte":
        clauses.append(f"CAST({ext} AS REAL) <= ?")
        params.append(val)
    elif op == "lt":
        clauses.append(f"CAST({ext} AS REAL) < ?")
        params.append(val)
    elif op == "ne":
        clauses.append(f"{ext} != ?")
        params.append(_param(val))
    elif op == "eq":
        clauses.append(f"{ext} = ?")
        params.append(_param(val))
    elif op == "in":
        if not isinstance(val, list) or not val:
            clauses.append("0 = 1")
        else:
            placeholders = ",".join("?" for _ in val)
            clauses.append(f"{ext} IN ({placeholders})")
            params.extend(str(v) for v in val)
    elif op == "prefix":
        clauses.append(f"{ext} LIKE ?")
        params.append(f"{val}%")
    elif op == "suffix":
        clauses.append(f"{ext} LIKE ?")
        params.append(f"%{val}")
    elif op == "contains":
        clauses.append(f"{ext} LIKE ?")
        params.append(f"%{val}%")
    elif op == "exists":
        if val:
            clauses.append(f"{ext} IS NOT NULL")
        else:
            clauses.append(f"{ext} IS NULL")
    else:
        raise FilterError(f"Unknown filter operator: {op!r}")


def _param(value: Any) -> Any:
    """Coerce a scalar to a SQLite-bindable form (matching JSON1 ->> output)."""
    if isinstance(value, bool):
        # JSON1 ->> renders booleans as 1/0 strings? Actually as the JSON literal "true"/"false".
        # Use the string form so equality compares the same way.
        return "true" if value else "false"
    if value is None:
        return None
    # JSON1's ->> always returns text for non-null scalars; equality works
    # naturally when we pass a string. For numbers, ->> returns the numeric
    # text representation, so str() lines up.
    return str(value)


# ---------------------------------------------------------------------------
# In-memory matcher — same semantics, for live subscriber filtering
# ---------------------------------------------------------------------------


def matches(data: dict, filter: dict[str, Any]) -> bool:
    """Evaluate the filter against an already-deserialized event dict."""
    if not filter:
        return True
    for key, expected in filter.items():
        actual = _walk_path(data, key)
        if not _match_value(actual, expected):
            return False
    return True


def _walk_path(data: Any, key: str) -> Any:
    cur = data
    for part in key.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _match_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        for op, val in expected.items():
            if not _match_op(actual, op, val):
                return False
        return True
    if isinstance(expected, list):
        return actual in expected
    if expected is None:
        return actual is None
    # Normalize for string-coerced storage compatibility.
    return str(actual) == str(expected) if actual is not None else False


def _match_op(actual: Any, op: str, val: Any) -> bool:
    if op == "exists":
        return (actual is not None) is bool(val)
    if actual is None:
        # null doesn't satisfy any other operator (consistent with SQL).
        return False
    if op == "eq":
        return str(actual) == str(val)
    if op == "ne":
        return str(actual) != str(val)
    if op == "in":
        return actual in (val or [])
    if op in _NUMERIC_OPS:
        try:
            a = float(actual)
            b = float(val)
        except (TypeError, ValueError):
            return False
        return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
    if op == "prefix":
        return isinstance(actual, str) and actual.startswith(str(val))
    if op == "suffix":
        return isinstance(actual, str) and actual.endswith(str(val))
    if op == "contains":
        return isinstance(actual, str) and str(val) in actual
    raise FilterError(f"Unknown filter operator: {op!r}")
