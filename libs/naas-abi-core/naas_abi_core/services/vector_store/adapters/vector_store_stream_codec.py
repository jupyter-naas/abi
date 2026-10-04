"""Frames of a streamed vector listing (docs/adr/20261003_nats-streamed-results.md).

Shared by the NATS primary and client; no new protobuf messages. Each frame
is a ``VectorPage`` holding documents only (no cursor), closed at about
``FRAME_BYTES`` of encoded documents.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from naas_abi_core.proto.vector_store.v1 import vector_store_pb2

FRAME_BYTES = 256 * 1024


def document_frames(
    documents: Iterable[vector_store_pb2.VectorDocument],
    frame_bytes: int = FRAME_BYTES,
) -> Iterator[bytes]:
    page, size = vector_store_pb2.VectorPage(), 0
    for document in documents:
        page.documents.append(document)
        size += document.ByteSize()
        if size >= frame_bytes:
            yield page.SerializeToString()
            page, size = vector_store_pb2.VectorPage(), 0
    if page.documents:
        yield page.SerializeToString()


def decode_frame(frame: bytes) -> list[vector_store_pb2.VectorDocument]:
    return list(vector_store_pb2.VectorPage.FromString(frame).documents)
