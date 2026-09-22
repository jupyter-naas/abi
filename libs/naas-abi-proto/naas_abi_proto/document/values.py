"""Lossless conversion of portable document values to their protobuf contract."""

import math
from datetime import datetime, timezone
from typing import Any

from naas_abi_proto.document.v1 import document_pb2 as pb


def encode_value(value: Any) -> pb.Value:
    if value is None:
        return pb.Value(null_value=True)
    if type(value) is bool:
        return pb.Value(bool_value=value)
    if type(value) is int:
        return pb.Value(int_value=value)
    if type(value) is float and math.isfinite(value):
        return pb.Value(float_value=value)
    if type(value) is str:
        if "\x00" in value:
            raise ValueError("Document strings cannot contain NUL")
        return pb.Value(string_value=value)
    if type(value) is bytes:
        return pb.Value(bytes_value=value)
    if isinstance(value, datetime) and value.utcoffset() is None:
        raise ValueError("Document datetimes must be timezone-aware")
    if isinstance(value, datetime):
        return pb.Value(datetime_value=value.astimezone(timezone.utc).isoformat())
    if isinstance(value, list):
        return pb.Value(list_value=pb.Values(items=[encode_value(v) for v in value]))
    if isinstance(value, dict):
        return pb.Value(object_value=encode_data(value))
    raise ValueError(f"Unsupported document value: {type(value).__name__}")


def decode_value(value: pb.Value) -> Any:
    kind = value.WhichOneof("kind")
    if kind is None:
        raise ValueError("Document value has no kind")
    if kind == "null_value":
        return None
    if kind == "datetime_value":
        result = datetime.fromisoformat(value.datetime_value)
        if result.utcoffset() is None:
            raise ValueError("Document datetimes must be timezone-aware")
        return result.astimezone(timezone.utc)
    if kind == "list_value":
        return [decode_value(v) for v in value.list_value.items]
    if kind == "object_value":
        return decode_data(value.object_value)
    return getattr(value, kind)


def encode_data(data: dict[str, Any]) -> pb.Data:
    if not isinstance(data, dict) or any(
        not isinstance(k, str) or "\x00" in k for k in data
    ):
        raise ValueError("Document data requires string keys without NUL")
    return pb.Data(fields={k: encode_value(v) for k, v in data.items()})


def decode_data(data: pb.Data) -> dict[str, Any]:
    return {k: decode_value(v) for k, v in data.fields.items()}
