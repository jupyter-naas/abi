"""Vector store values on the wire, shared by the NATS primary and client.

Vectors are ``VectorData`` (32-bit floats); metadata, payloads and filters
are JSON objects (naas_abi_proto/vector_store/values.py), so integers stay
exact and nested values stay plain.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from naas_abi_core.proto.vector_store.v1 import vector_store_pb2
from naas_abi_core.services.vector_store.IVectorStorePort import (
    SearchResult,
    VectorDocument,
)
from naas_abi_proto.vector_store.values import decode_object, encode_object


def vector_to_pb(vector: np.ndarray | None) -> vector_store_pb2.VectorData | None:
    # None leaves an `optional` message field unset (HasField stays False).
    if vector is None:
        return None
    return vector_store_pb2.VectorData(values=[float(v) for v in vector.tolist()])


def pb_to_vector(pb: vector_store_pb2.VectorData) -> np.ndarray:
    return np.array(list(pb.values), dtype=np.float32)


def object_to_pb(value: dict[str, Any] | None) -> bytes | None:
    """A JSON object field; ``None`` leaves an ``optional`` field unset."""
    return None if value is None else encode_object(value)


def pb_to_object(message: Any, field: str) -> dict[str, Any] | None:
    """An ``optional`` JSON object field, ``None`` when unset."""
    return decode_object(getattr(message, field)) if message.HasField(field) else None


def document_to_pb(document: VectorDocument) -> vector_store_pb2.VectorDocument:
    return vector_store_pb2.VectorDocument(
        id=document.id,
        vector=vector_to_pb(document.vector),
        metadata=encode_object(document.metadata or {}),
        payload=object_to_pb(document.payload),
    )


def pb_to_document(pb: vector_store_pb2.VectorDocument) -> VectorDocument:
    return VectorDocument(
        id=pb.id,
        vector=pb_to_vector(pb.vector) if pb.HasField("vector") else np.array([]),
        metadata=decode_object(pb.metadata),
        payload=pb_to_object(pb, "payload"),
    )


def search_result_to_pb(result: SearchResult) -> vector_store_pb2.SearchResult:
    return vector_store_pb2.SearchResult(
        id=result.id,
        score=result.score,
        vector=vector_to_pb(result.vector),
        metadata=object_to_pb(result.metadata),
        payload=object_to_pb(result.payload),
    )


def pb_to_search_result(pb: vector_store_pb2.SearchResult) -> SearchResult:
    return SearchResult(
        id=pb.id,
        score=pb.score,
        vector=pb_to_vector(pb.vector) if pb.HasField("vector") else None,
        metadata=pb_to_object(pb, "metadata"),
        payload=pb_to_object(pb, "payload"),
    )
