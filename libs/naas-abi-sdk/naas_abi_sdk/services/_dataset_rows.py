"""Dataset rows on the wire; mirrors core's dataset_row_codec (the SDK stays
core-free).

Rows travel as UTF-8 JSON objects (``json_rows``): integers stay integers,
exact at any size. ``google.protobuf.Struct`` (``rows``) stores every number
as a double; it remains for engines that predate ``json_rows``: reads fall
back to it, and writes carry both encodings (an older engine ignores
``json_rows`` and would otherwise write nothing).
"""

from __future__ import annotations

import base64
import json
from decimal import Decimal
from typing import Any

from google.protobuf import json_format


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def encode_row(row: dict[str, Any]) -> bytes:
    return json.dumps(
        row, default=_json_value, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def struct_row(row: dict[str, Any]) -> dict[str, Any]:
    # Struct takes JSON-compatible values only; make them so first.
    return json.loads(encode_row(row))


def decode_rows(result: Any) -> list[dict[str, Any]]:
    """The rows of a ``dataset.v1.QueryResult``."""
    if result.json_rows:
        return [json.loads(row) for row in result.json_rows]
    return [json_format.MessageToDict(row) for row in result.rows]
