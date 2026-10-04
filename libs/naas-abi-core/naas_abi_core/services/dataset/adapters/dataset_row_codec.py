"""Dataset rows on the wire, shared by the NATS primary and client.

Rows travel as UTF-8 JSON objects (``json_rows``): integers stay integers,
exact at any size. ``google.protobuf.Struct`` (``rows``) stores every number as
a double, so 42 came back as 42.0 and integers above 2^53 lost precision; it
remains for peers that predate ``json_rows``: a request that does not set
``accept_json_rows`` gets Struct rows, and writes carry both encodings (an
older server ignores ``json_rows`` and would otherwise write nothing).
"""

from __future__ import annotations

import base64
import json
from decimal import Decimal
from typing import Any

from google.protobuf import json_format
from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.services.dataset.DatasetPort import QueryResult


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


def decode_row(data: bytes) -> dict[str, Any]:
    return json.loads(data)


def _struct_row(row: dict[str, Any]) -> dict[str, Any]:
    # Struct takes JSON-compatible values only; make them so first.
    return json.loads(encode_row(row))


def query_result_to_pb(
    result: QueryResult, *, json_rows: bool
) -> dataset_pb2.QueryResult:
    if json_rows:
        return dataset_pb2.QueryResult(
            columns=result.columns, json_rows=[encode_row(row) for row in result.rows]
        )
    return dataset_pb2.QueryResult(
        columns=result.columns, rows=[_struct_row(row) for row in result.rows]
    )


def query_result_from_pb(pb: dataset_pb2.QueryResult) -> QueryResult:
    if pb.json_rows:
        rows = [decode_row(row) for row in pb.json_rows]
    else:  # a server that predates json_rows
        rows = [json_format.MessageToDict(row) for row in pb.rows]
    return QueryResult(columns=list(pb.columns), rows=rows)


def write_rows_to_pb(
    request: dataset_pb2.WriteRequest, rows: list[dict[str, Any]]
) -> None:
    request.json_rows.extend(encode_row(row) for row in rows)
    for row in rows:
        request.rows.add().update(_struct_row(row))


def write_rows_from_pb(request: dataset_pb2.WriteRequest) -> list[dict[str, Any]]:
    if request.json_rows:
        return [decode_row(row) for row in request.json_rows]
    return [json_format.MessageToDict(row) for row in request.rows]  # an older client
