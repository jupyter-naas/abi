"""Dataset rows over NATS, shared by the primary and the client.

Each row crosses as one UTF-8 JSON object (naas_abi_proto/dataset/rows.py),
holding the values of DatasetValues.py.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.services.dataset.DatasetPort import DatasetSchemaError, QueryResult
from naas_abi_proto.dataset.rows import decode_row, encode_row


def encode_rows(rows: list[dict[str, Any]]) -> list[bytes]:
    encoded = []
    for index, row in enumerate(rows):
        try:
            encoded.append(encode_row(row))
        except ValueError as exc:  # NaN or an infinity
            raise DatasetSchemaError(
                f"Row {index} holds a number that is not finite"
            ) from exc
    return encoded


def decode_rows(rows: Any) -> list[dict[str, Any]]:
    return [decode_row(row) for row in rows]


def query_result_to_pb(result: QueryResult) -> dataset_pb2.QueryResult:
    return dataset_pb2.QueryResult(
        columns=result.columns, rows=encode_rows(result.rows)
    )


def query_result_from_pb(pb: dataset_pb2.QueryResult) -> QueryResult:
    return QueryResult(columns=list(pb.columns), rows=decode_rows(pb.rows))
