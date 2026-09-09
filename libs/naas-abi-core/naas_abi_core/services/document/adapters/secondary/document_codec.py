"""Value/type-preserving JSON encoding. Object key order is not a contract."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any, cast

from naas_abi_core.services.document.DocumentPort import Value


class ValueKind(IntEnum):
    NULL = 0
    BOOL = 1
    NUMBER = 2
    STRING = 3
    DATETIME = 4
    BYTES = 5
    ARRAY = 6
    OBJECT = 7


def bytes_sort_key(value: bytes) -> str:
    return value.hex()


def encoded_bytes_sort_key(value: str | None) -> str:
    return bytes_sort_key(base64.b64decode(value, validate=True)) if value else ""


def value_sort_parts(value: Value) -> tuple[int, int | float, str]:
    if value is None:
        return (ValueKind.NULL, 0, "")
    if isinstance(value, bool):
        return (ValueKind.BOOL, int(value), "")
    if isinstance(value, (int, float)):
        return (ValueKind.NUMBER, value, "")
    if isinstance(value, str):
        return (ValueKind.STRING, 0, value)
    if isinstance(value, datetime):
        return (ValueKind.DATETIME, 0, encode(value)["$v"])
    if isinstance(value, bytes):
        return (ValueKind.BYTES, 0, bytes_sort_key(value))
    return (ValueKind.ARRAY if isinstance(value, list) else ValueKind.OBJECT, 0, "")


def storage_key(key: str) -> str:
    return "$" + key if key.startswith("$") else key


def encode(value: Value) -> Any:
    if isinstance(value, datetime):
        return {
            "$t": "datetime",
            "$v": value.astimezone(UTC).isoformat(timespec="microseconds"),
        }
    if isinstance(value, bytes):
        return {"$t": "bytes", "$v": base64.b64encode(value).decode("ascii")}
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {storage_key(key): encode(item) for key, item in value.items()}
    return value


def decode(value: Any) -> Value:
    if isinstance(value, dict):
        if value.get("$t") == "datetime":
            return datetime.fromisoformat(value["$v"])
        if value.get("$t") == "bytes":
            return base64.b64decode(value["$v"], validate=True)
        return {
            key[1:] if key.startswith("$$") else key: decode(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [decode(item) for item in value]
    return cast(Value, value)


def dumps(value: Any) -> str:
    """Canonical object serialization for equality, indexes, and cursors."""
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sqlite_field(raw: str, key: str) -> str | None:
    """Look up a literal key, including quotes/backslashes on older SQLite."""
    data = json.loads(raw)
    return dumps(data[key]) if key in data else None


def equality_key(value: Any) -> Any:
    """Match JSONB equality: numeric 1 == 1.0, but true != 1, recursively."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [equality_key(item) for item in value]
    if isinstance(value, dict):
        return {key: equality_key(item) for key, item in value.items()}
    return value


def sqlite_json_key(raw: str | None) -> str | None:
    if raw is None or raw == "null":
        return None
    return dumps(equality_key(json.loads(raw)))


def sqlite_equal(left: str | None, right: str) -> bool:
    if left is None:
        return False
    return dumps(equality_key(json.loads(left))) == dumps(
        equality_key(json.loads(right))
    )
