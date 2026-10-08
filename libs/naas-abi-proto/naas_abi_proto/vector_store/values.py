"""Vector store metadata, payloads and filters on the wire: one JSON object as
UTF-8 bytes.

``google.protobuf.Struct`` made every number a double (42 came back as 42.0,
integers above 2^53 rounded) and nested values arrived as Struct objects. JSON
keeps integers exact and nested values plain. Values with no JSON form take a
portable one: numpy scalars their Python value, dates and times their ISO-8601
string, ``Decimal`` a float, bytes base64, anything else its string form. NaN
and infinities have no JSON form and are refused.
"""

import base64
import json
from decimal import Decimal
from typing import Any


# The proto fields holding one JSON object each, by message: shared by every
# reader and writer (core codec, SDK codec, SDK DTO generator).
JSON_OBJECT_FIELDS: dict[str, tuple[str, ...]] = {
    "abi.vector_store.v1.VectorDocument": ("metadata", "payload"),
    "abi.vector_store.v1.SearchResult": ("metadata", "payload"),
    "abi.vector_store.v1.SearchRequest": ("filter",),
    "abi.vector_store.v1.UpdateVectorRequest": ("metadata", "payload"),
}


def _portable(value: Any) -> Any:
    if hasattr(value, "item"):  # numpy scalars, without importing numpy
        return value.item()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def encode_object(value: dict[str, Any]) -> bytes:
    """Raises ``ValueError`` for NaN or an infinity."""
    return json.dumps(
        value,
        default=_portable,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_object(data: bytes) -> dict[str, Any]:
    """The object ``encode_object`` wrote; empty bytes are an empty object."""
    if not data:
        return {}
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value
