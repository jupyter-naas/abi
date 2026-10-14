"""Dataset rows on the wire: one UTF-8 JSON object per row.

``QueryResult.rows`` and ``WriteRequest.rows`` carry these bytes. JSON numbers
keep integers exact at any size, and any language can read the rows. Values
with no JSON form take a portable one: dates and times their ISO-8601 string,
``Decimal`` a float, bytes base64, anything else its string form. NaN and
infinities have no JSON form and are refused.
"""

import base64
import json
from decimal import Decimal
from typing import Any


def _portable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def encode_row(row: dict[str, Any]) -> bytes:
    """Raises ``ValueError`` for NaN or an infinity."""
    return json.dumps(
        row,
        default=_portable,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_row(data: bytes) -> dict[str, Any]:
    return json.loads(data)
