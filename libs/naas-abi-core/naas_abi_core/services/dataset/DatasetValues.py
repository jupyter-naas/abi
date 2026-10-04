"""The values a dataset row holds, the same for every adapter and transport.

Rows hold JSON values: ``None``, ``bool``, ``int`` (exact at any size),
finite ``float``, ``str``, and ``dict``/``list`` (JSON columns and nested
results). A backend value with no JSON form takes a portable one:

- dates, timestamps and times: their ISO-8601 string (``datetime.isoformat``);
- ``Decimal``: a float;
- bytes: a base64 string;
- NaN and infinities: ``None``;
- anything else (UUID, interval, ...): its string form.

Writes accept the same values, plus ``date``/``datetime`` objects for date
and timestamp columns; NaN and infinities are refused, since they have no
JSON form. Timestamps are stored in UTC: a value with an offset (a
``datetime`` or an ISO-8601 string, ``Z`` included) is converted, a naive one
is taken as UTC (``timestamp_value``); they read back without an offset. Every adapter holds to this (tests/dataset__secondary_adapter__generic_test.py).
"""

from __future__ import annotations

import base64
import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def is_finite(value: Any) -> bool:
    """False for a NaN or infinite float or Decimal, True for anything else."""
    if isinstance(value, (float, Decimal)):
        return math.isfinite(value)
    return True


def row_value(value: Any) -> Any:
    """``value`` in its portable form (module docstring)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, (float, Decimal)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): row_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [row_value(item) for item in value]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def timestamp_value(value: Any) -> Any:
    """A timestamp column's value as stored: UTC, without an offset.

    A ``datetime`` or ISO-8601 string with an offset is converted; a naive
    value is taken as UTC and kept; anything else is left for the backend to
    cast or refuse.
    """
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        if parsed.tzinfo is None:
            return value
        value = parsed
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value
