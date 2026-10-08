"""NATS RPC client adapter for the vector_store kernel domain.

Implements ``IVectorStorePort`` by calling out to a remote
``VectorStorePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/vector_store/v1/vector_store.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
by the transport after failure; a timeout may hide a completed operation.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``VectorStorePrimaryAdapterNATS`` must read the token
from that exact header -- both sides read ``AUTH_HEADER`` from
``vector_store_nats_contract``, a neutral module neither adapter owns, so
this file never has to import from the primary adapter's module (or vice
versa) just to agree on a header name.

This client targets the raw ``IVectorStorePort`` -- the same as every other
concrete adapter here (Qdrant, QdrantInMemory, SqliteVec) -- and is plugged
into ``VectorStoreService(adapter=...)`` exactly like them. The richer
domain methods (``ensure_collection``, ``add_documents``, ``search_similar``,
...) live entirely in ``VectorStoreService`` and stay unaffected by this
client except that each underlying port call now goes over the network.

``create_collection``'s ``**kwargs`` is deliberately not part of this wire
contract -- see the ``.proto`` file's header comment for why. If a caller
ever passes one, this client raises ``NotImplementedError`` rather than
silently dropping it (the same "reject explicitly, never silently degrade"
stance ``ObjectStorageSecondaryAdapterNATSClient`` takes on its two
streaming methods).

``close()`` is a special case worth flagging up front: it does NOT invoke
the ``close`` RPC. See its docstring below -- in short, the adapter behind
``VectorStorePrimaryAdapterNATS`` is shared across every concurrent caller,
so one caller's ``close()`` must only release *that caller's* NATS
connection, never the shared store connection underneath the server.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.vector_store.v1 import vector_store_pb2
from naas_abi_core.services.vector_store.adapters.vector_store_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.vector_store.IVectorStorePort import (
    IVectorStorePort,
    SearchResult,
    VectorDocument,
)


def _vector_to_pb(vector: np.ndarray | None) -> vector_store_pb2.VectorData | None:
    if vector is None:
        return None
    return vector_store_pb2.VectorData(values=[float(v) for v in vector.tolist()])


def _pb_to_vector(pb: vector_store_pb2.VectorData) -> np.ndarray:
    return np.array(list(pb.values), dtype=np.float32)


def _document_to_pb(document: VectorDocument) -> vector_store_pb2.VectorDocument:
    return vector_store_pb2.VectorDocument(
        id=document.id,
        vector=_vector_to_pb(document.vector),
        metadata=document.metadata,
        payload=document.payload,
    )


def _pb_to_document(pb: vector_store_pb2.VectorDocument) -> VectorDocument:
    return VectorDocument(
        id=pb.id,
        vector=_pb_to_vector(pb.vector) if pb.HasField("vector") else np.array([]),
        metadata=dict(pb.metadata),
        payload=dict(pb.payload) if pb.HasField("payload") else None,
    )


def _pb_to_search_result(pb: vector_store_pb2.SearchResult) -> SearchResult:
    return SearchResult(
        id=pb.id,
        score=pb.score,
        vector=_pb_to_vector(pb.vector) if pb.HasField("vector") else None,
        metadata=dict(pb.metadata) if pb.HasField("metadata") else None,
        payload=dict(pb.payload) if pb.HasField("payload") else None,
    )


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    ``IVectorStorePort`` declares no typed exceptions of its own -- see
    ``VectorStorePrimaryAdapterNATS``'s module docstring -- so unlike
    ``ObjectStorageSecondaryAdapterNATSClient._raise_for_error`` there is no
    known-domain-exception branch here: every server-reported failure other
    than an auth failure surfaces as a plain ``RuntimeError`` carrying the
    wire code, matching what an in-process adapter failure would look like
    to ``VectorStoreService`` (a bare exception it republishes as a
    ``VectorStoreError`` event and reraises).
    """
    raise RuntimeError(f"vector_store NATS RPC failed ({error.code}): {error.message}")


class VectorStoreSecondaryAdapterNATSClient(NatsRPCClient, IVectorStorePort):
    """Calls a remote ``VectorStorePrimaryAdapterNATS`` over NATS RPC."""

    def __init__(
        self,
        nats_url: str,
        jwt_secret: str,
        service_identity: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        super().__init__(
            nats_url,
            jwt_secret,
            service_identity,
            timeout_seconds,
            auth_header=AUTH_HEADER,
        )

    def close(self) -> None:
        """Release this client's transport; never close the shared remote store."""
        super().close()

    # ------------------------------------------------------------------
    # IVectorStorePort.
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        request = vector_store_pb2.InitializeRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.initialize", request, vector_store_pb2.InitializeResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs: Any,
    ) -> None:
        if kwargs:
            raise NotImplementedError(
                "VectorStoreSecondaryAdapterNATSClient.create_collection does not "
                "support adapter-specific kwargs: they are out of scope for the v1 "
                f"vector_store NATS RPC contract. Got: {sorted(kwargs)}"
            )
        request = vector_store_pb2.CreateCollectionRequest(
            context=self._context(),
            collection_name=collection_name,
            dimension=dimension,
            distance_metric=distance_metric,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.create_collection",
            request,
            vector_store_pb2.CreateCollectionResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def delete_collection(self, collection_name: str) -> None:
        request = vector_store_pb2.DeleteCollectionRequest(
            context=self._context(), collection_name=collection_name
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.delete_collection",
            request,
            vector_store_pb2.DeleteCollectionResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def list_collections(self) -> list[str]:
        request = vector_store_pb2.ListCollectionsRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.list_collections",
            request,
            vector_store_pb2.ListCollectionsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return list(response.collections.names)

    def store_vectors(
        self, collection_name: str, documents: list[VectorDocument]
    ) -> None:
        request = vector_store_pb2.StoreVectorsRequest(
            context=self._context(),
            collection_name=collection_name,
            documents=[_document_to_pb(doc) for doc in documents],
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.store_vectors",
            request,
            vector_store_pb2.StoreVectorsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: dict[str, Any] | None = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> list[SearchResult]:
        request = vector_store_pb2.SearchRequest(
            context=self._context(),
            collection_name=collection_name,
            query_vector=[float(v) for v in query_vector.tolist()],
            k=k,
            filter=filter,
            include_vectors=include_vectors,
            include_metadata=include_metadata,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.search", request, vector_store_pb2.SearchResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_search_result(result) for result in response.results.results]

    def get_vector(
        self, collection_name: str, vector_id: str, include_vector: bool = True
    ) -> VectorDocument | None:
        request = vector_store_pb2.GetVectorRequest(
            context=self._context(),
            collection_name=collection_name,
            vector_id=vector_id,
            include_vector=include_vector,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_vector", request, vector_store_pb2.GetVectorResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        if not response.found.HasField("document"):
            return None
        return _pb_to_document(response.found.document)

    def update_vector(
        self,
        collection_name: str,
        vector_id: str,
        vector: np.ndarray | None = None,
        metadata: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        request = vector_store_pb2.UpdateVectorRequest(
            context=self._context(),
            collection_name=collection_name,
            vector_id=vector_id,
            vector=_vector_to_pb(vector),
            metadata=metadata,
            payload=payload,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.update_vector",
            request,
            vector_store_pb2.UpdateVectorResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def delete_vectors(self, collection_name: str, vector_ids: list[str]) -> None:
        request = vector_store_pb2.DeleteVectorsRequest(
            context=self._context(),
            collection_name=collection_name,
            vector_ids=vector_ids,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.delete_vectors",
            request,
            vector_store_pb2.DeleteVectorsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def count_vectors(self, collection_name: str) -> int:
        request = vector_store_pb2.CountVectorsRequest(
            context=self._context(), collection_name=collection_name
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.count_vectors",
            request,
            vector_store_pb2.CountVectorsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.count

    # Note: `close()` (IVectorStorePort's close, not a network call) is
    # defined once already, up in the connection-lifecycle section above --
    # see that method's docstring for why this client never sends the
    # `close` RPC itself.
