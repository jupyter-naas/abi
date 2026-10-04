"""EventBridge-style filters on an event's fields (``OnEvent(filter=...)``).

Mirrors ``naas_abi_core.services.event.EventFilter.matches`` (the SDK stays
core-free); change them together. A filter maps dotted paths in the event's
JSON to a scalar (equals), a list (in) or an operator dict (``eq``, ``ne``,
``in``, ``gt``, ``gte``, ``lt``, ``lte``, ``prefix``, ``suffix``, ``contains``,
``exists``); keys are AND-joined.
"""

from __future__ import annotations

import re
from typing import Any

_PATH = re.compile(r"^[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*$")
_NUMERIC_OPS = {"gt", "gte", "lt", "lte"}
OPERATORS = _NUMERIC_OPS | {"eq", "ne", "in", "prefix", "suffix", "contains", "exists"}


def validate(filter: Any) -> dict[str, Any]:
    """The filter, checked: a dict of dotted paths to known matchers."""
    if not isinstance(filter, dict):
        raise TypeError("An event filter is a dict of field paths to matchers")
    for key, expected in filter.items():
        if not isinstance(key, str) or not _PATH.match(key):
            raise ValueError(f"Invalid event filter path: {key!r}")
        if isinstance(expected, dict):
            unknown = set(expected) - OPERATORS
            if unknown:
                raise ValueError(f"Unknown event filter operator(s): {sorted(unknown)}")
    return filter


def matches(data: Any, filter: dict[str, Any] | None) -> bool:
    """Whether an event (its decoded JSON) passes the filter; no filter passes all."""
    if not filter:
        return True
    if not isinstance(data, dict):
        return False
    return all(
        _match_value(_walk(data, key), expected) for key, expected in filter.items()
    )


def _walk(data: Any, key: str) -> Any:
    current = data
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _match_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return all(_match_op(actual, op, value) for op, value in expected.items())
    if isinstance(expected, list):
        return actual in expected
    if expected is None:
        return actual is None
    return actual is not None and str(actual) == str(expected)


def _match_op(actual: Any, op: str, value: Any) -> bool:
    if op == "exists":
        return (actual is not None) is bool(value)
    if actual is None:
        return False
    if op == "eq":
        return str(actual) == str(value)
    if op == "ne":
        return str(actual) != str(value)
    if op == "in":
        return actual in (value or [])
    if op in _NUMERIC_OPS:
        try:
            a, b = float(actual), float(value)
        except (TypeError, ValueError):
            return False
        return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
    if op == "prefix":
        return isinstance(actual, str) and actual.startswith(str(value))
    if op == "suffix":
        return isinstance(actual, str) and actual.endswith(str(value))
    if op == "contains":
        return isinstance(actual, str) and str(value) in actual
    raise ValueError(f"Unknown event filter operator: {op!r}")
