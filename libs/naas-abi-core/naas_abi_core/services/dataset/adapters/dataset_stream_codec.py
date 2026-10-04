"""Frames of a streamed dataset query (docs/adr/20261003_nats-streamed-results.md).

Shared by the NATS primary and client; no new protobuf messages. The first
frame is a ``QueryResult`` with the columns only, then each frame is a
``QueryResult`` with rows only, as JSON rows (dataset_row_codec.py).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.services.dataset.adapters.dataset_row_codec import (
    encode_row,
    query_result_from_pb,
)

FRAME_BYTES = 256 * 1024


def encode_header(columns: list[str]) -> bytes:
    return dataset_pb2.QueryResult(columns=columns).SerializeToString()


def decode_header(frame: bytes) -> list[str]:
    return list(dataset_pb2.QueryResult.FromString(frame).columns)


def row_frames(
    rows: Iterable[dict[str, Any]], frame_bytes: int = FRAME_BYTES
) -> Iterator[bytes]:
    batch, size = dataset_pb2.QueryResult(), 0
    for row in rows:
        encoded = encode_row(row)
        batch.json_rows.append(encoded)
        size += len(encoded)
        if size >= frame_bytes:
            yield batch.SerializeToString()
            batch, size = dataset_pb2.QueryResult(), 0
    if batch.json_rows:
        yield batch.SerializeToString()


def decode_rows(frame: bytes) -> list[dict[str, Any]]:
    return query_result_from_pb(dataset_pb2.QueryResult.FromString(frame)).rows
