"""Internal transport conversion. Public proxies expose Python data only."""

from __future__ import annotations

import importlib
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

from google.protobuf import json_format
from google.protobuf.message import Message

from naas_abi_sdk.services.errors import domain_error
from naas_abi_sdk.services.models import DTO_TYPES
from naas_abi_sdk.transport import RPCError


def message(cls, values):
    if isinstance(values, Message):
        return values
    if is_dataclass(values):
        values = asdict(values)
    full = cls.DESCRIPTOR.full_name
    if full == "google.protobuf.Timestamp":
        if not isinstance(values, datetime) or values.utcoffset() is None:
            raise ValueError("Timestamps must be timezone-aware datetimes")
        result = cls()
        result.FromDatetime(values)
        return result
    if full == "google.protobuf.Struct":
        return json_format.ParseDict(values, cls())
    if full == "abi.vector_store.v1.VectorData":
        values = {"values": [float(v) for v in values]}
    result = cls()
    for name, value in values.items():
        if value is None:
            continue
        field = cls.DESCRIPTOR.fields_by_name.get(name)
        if field is None:
            raise TypeError(f"{cls.__name__} has no field {name}")
        if field.message_type:
            if field.message_type.GetOptions().map_entry:
                getattr(result, name).update(value)
                continue
            child = getattr(result, name)
            if field.is_repeated:
                for item in value:
                    entry = child.add()
                    entry.CopyFrom(message(type(entry), item))
            else:
                child.CopyFrom(message(type(child), value))
        elif field.enum_type:
            if isinstance(value, str):
                prefix = {
                    "ColumnType": "COLUMN_TYPE_",
                    "PartitionTransform": "PARTITION_TRANSFORM_",
                    "WriteMode": "WRITE_MODE_",
                }.get(field.enum_type.name, "")
                value = field.enum_type.values_by_name[prefix + value.upper()].number
            setattr(result, name, value)
        elif field.is_repeated:
            getattr(result, name).extend(value)
        else:
            setattr(result, name, value)
    return result


def decode(value):
    if not isinstance(value, Message):
        return value
    name = value.DESCRIPTOR.full_name
    if name == "google.protobuf.Timestamp":
        return value.ToDatetime(tzinfo=timezone.utc)
    if name == "google.protobuf.Struct":
        return json_format.MessageToDict(value)
    if name == "abi.vector_store.v1.VectorData":
        return list(value.values)
    data = {}
    for field in value.DESCRIPTOR.fields:
        if field.name == "error" or field.name.endswith("_detail"):
            continue
        raw = getattr(value, field.name)
        if field.is_repeated:
            data[field.name] = (
                dict(raw)
                if field.message_type and field.message_type.GetOptions().map_entry
                else [decode(v) for v in raw]
            )
        elif field.has_presence and not value.HasField(field.name):
            data[field.name] = None
        elif field.enum_type:
            raw = field.enum_type.values_by_number[raw].name
            for prefix in ("COLUMN_TYPE_", "PARTITION_TRANSFORM_", "WRITE_MODE_"):
                raw = raw.removeprefix(prefix)
            data[field.name] = raw.lower()
        else:
            data[field.name] = decode(raw)
    if name in DTO_TYPES:
        return DTO_TYPES[name](**data)
    if len(data) == 1:
        return next(iter(data.values()))
    return data or None


class ServiceProxy:
    domain: str

    def __init__(self, client):
        self._client = client

    async def _request(self, operation: str, **values: Any):
        pb = importlib.import_module(
            f"naas_abi_proto.{self.domain}.v1.{self.domain}_pb2"
        )
        cls = getattr(pb, "".join(p.title() for p in operation.split("_")) + "Request")
        if self.domain == "activity_log" and operation == "query":
            values["filter"] = values.pop("query")
        if self.domain == "source_control" and operation == "upsert_file":
            content = values.pop("content")
            values[
                "binary_content" if isinstance(content, bytes) else "text_content"
            ] = content
        if self.domain == "source_control" and operation == "upsert_files":
            values["files"] = [
                {
                    "path": f.path,
                    "binary_content"
                    if isinstance(f.content, bytes)
                    else "text_content": f.content,
                }
                for f in values["files"]
            ]
        if self.domain == "email":
            for key in ("to_emails", "cc_emails"):
                if isinstance(values.get(key), str):
                    values[key] = [
                        v.strip() for v in values[key].split(",") if v.strip()
                    ]
        request = message(cls, values)
        try:
            response = await getattr(self._client, operation)(request)
        except RPCError as exc:
            raise domain_error(exc) from exc
        return decode(response)
