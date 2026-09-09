"""Lossless JSON encoding shared by the SQL adapters, including escaped tag keys."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any, cast

from naas_abi_core.services.document.DocumentPort import Value


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
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


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
