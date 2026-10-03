"""Frames of a streamed dataset query (docs/adr/20261003_nats-streamed-results.md).

Shared by the NATS primary and client; no new protobuf messages. The first
frame is a ``QueryResult`` with the columns only, then each frame is a
``QueryResult`` with rows only (``Struct``s, as the unary ``query`` reply).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from google.protobuf import json_format
from naas_abi_core.proto.dataset.v1 import dataset_pb2

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
        struct = batch.rows.add()
        struct.update(row)
        size += struct.ByteSize()
        if size >= frame_bytes:
            yield batch.SerializeToString()
            batch, size = dataset_pb2.QueryResult(), 0
    if batch.rows:
        yield batch.SerializeToString()


def decode_rows(frame: bytes) -> list[dict[str, Any]]:
    return [
        json_format.MessageToDict(row)
        for row in dataset_pb2.QueryResult.FromString(frame).rows
    ]
