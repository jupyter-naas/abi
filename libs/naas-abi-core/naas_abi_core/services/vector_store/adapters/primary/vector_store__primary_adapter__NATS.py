"""NATS RPC primary adapter for the vector_store kernel domain.

Exposes a real ``IVectorStorePort`` as a NATS micro-service (see
``naas_abi_core/proto/vector_store/v1/vector_store.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there). This
is the server side; the matching client is
``VectorStoreSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``vector_store_nats_contract`` below -- that's
a neutral module neither adapter owns, so this file and the client's don't
depend on each other; see that module's docstring for why).

Unlike ``ObjectStoragePrimaryAdapterNATS``, this adapter wraps a raw
``IVectorStorePort`` implementation directly, not the ``VectorStoreService``
domain wrapper: ``VectorStoreService`` composes an ``IVectorStorePort``
adapter (it does not subclass the port) and layers on richer, event-publishing
methods (``ensure_collection``, ``add_documents``, ``search_similar``, ...)
that are NOT part of ``IVectorStorePort`` and so have no endpoint here at all.
Those richer methods stay entirely local to whichever process holds the
domain service, composed from calls to the (possibly now-remote) port
methods below -- exactly like every other concrete ``IVectorStorePort``
adapter (Qdrant, QdrantInMemory, SqliteVec) is wrapped by
``VectorStoreService(adapter=...)`` today.

``create_collection``'s ``**kwargs`` is deliberately not part of this
contract -- see the ``.proto`` file's header comment -- so the endpoint below
never passes any.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

import nats
import nats.micro
import numpy as np
from google.protobuf.message import DecodeError, Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_rpc import respond_protobuf
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.vector_store.v1 import vector_store_pb2
from naas_abi_core.services.vector_store.adapters.vector_store_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.vector_store.IVectorStorePort import (
    IVectorStorePort,
    SearchResult,
    VectorDocument,
)
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "VectorStorePrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


def _vector_to_pb(vector: np.ndarray | None) -> vector_store_pb2.VectorData | None:
    # Passing None for an `optional` message-typed constructor kwarg leaves
    # the field unset (HasField stays False) rather than setting it to some
    # default instance -- verified against the generated bindings, the same
    # convention relied on throughout this module.
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


def _search_result_to_pb(result: SearchResult) -> vector_store_pb2.SearchResult:
    return vector_store_pb2.SearchResult(
        id=result.id,
        score=result.score,
        vector=_vector_to_pb(result.vector),
        metadata=result.metadata,
        payload=result.payload,
    )


class VectorStorePrimaryAdapterNATS:
    """Serves a raw ``IVectorStorePort`` over NATS RPC (request/reply).

    Registers one NATS micro-service endpoint per ``IVectorStorePort``
    method. Each endpoint authenticates the caller via ``Nats-Auth-Token``
    before doing anything else, then decodes the Protobuf request, calls
    straight through to the wrapped adapter, and encodes a Protobuf
    response. Errors -- auth failures, anything unexpected -- are always
    reported as a normal response carrying a populated ``CallError``, never
    as a crashed handler or a raw NATS-level error.

    ``IVectorStorePort`` declares no typed exceptions of its own (see
    ``VectorStoreService`` -- every adapter call it makes is wrapped in a
    bare ``except Exception`` that republishes a ``VectorStoreError`` event
    and reraises), so unlike ``ObjectStoragePrimaryAdapterNATS`` there is no
    known-exception branch to map here: every failure maps to ``INTERNAL``.
    """

    def __init__(
        self,
        adapter: IVectorStorePort,
        jwt_secret: str,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``vector_store`` NATS service on ``nc``.

        ``nc`` must already be connected -- this adapter never manages the
        connection lifecycle itself, only the service/endpoints layered on
        top of it. Calling this more than once is a no-op.
        """
        if self._service is not None:
            return

        service = await nats.micro.add_service(
            nc,
            name=SERVICE_NAME,
            version=SERVICE_VERSION,
            description="ABI kernel vector_store domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="initialize",
            subject=f"{SUBJECT_PREFIX}.initialize",
            handler=self._handle_initialize,
        )
        await service.add_endpoint(
            name="create_collection",
            subject=f"{SUBJECT_PREFIX}.create_collection",
            handler=self._handle_create_collection,
        )
        await service.add_endpoint(
            name="delete_collection",
            subject=f"{SUBJECT_PREFIX}.delete_collection",
            handler=self._handle_delete_collection,
        )
        await service.add_endpoint(
            name="list_collections",
            subject=f"{SUBJECT_PREFIX}.list_collections",
            handler=self._handle_list_collections,
        )
        await service.add_endpoint(
            name="store_vectors",
            subject=f"{SUBJECT_PREFIX}.store_vectors",
            handler=self._handle_store_vectors,
        )
        await service.add_endpoint(
            name="search",
            subject=f"{SUBJECT_PREFIX}.search",
            handler=self._handle_search,
        )
        await service.add_endpoint(
            name="get_vector",
            subject=f"{SUBJECT_PREFIX}.get_vector",
            handler=self._handle_get_vector,
        )
        await service.add_endpoint(
            name="update_vector",
            subject=f"{SUBJECT_PREFIX}.update_vector",
            handler=self._handle_update_vector,
        )
        await service.add_endpoint(
            name="delete_vectors",
            subject=f"{SUBJECT_PREFIX}.delete_vectors",
            handler=self._handle_delete_vectors,
        )
        await service.add_endpoint(
            name="count_vectors",
            subject=f"{SUBJECT_PREFIX}.count_vectors",
            handler=self._handle_count_vectors,
        )
        await service.add_endpoint(
            name="close",
            subject=f"{SUBJECT_PREFIX}.close",
            handler=self._handle_close,
        )
        self._service = service

    async def stop(self) -> None:
        """Deregister the service, draining its subscriptions."""
        service = self._service
        self._service = None
        if service is not None:
            await service.stop()

    # ------------------------------------------------------------------
    # Shared request handling: auth, decode, dispatch, encode.
    # ------------------------------------------------------------------

    async def _handle(
        self,
        request: Request,
        request_cls: type[_RequestT],
        response_cls: Callable[..., _ResponseT],
        call: Callable[[_RequestT], _ResponseT],
    ) -> None:
        if not self._is_authenticated(request):
            await self._respond_error(
                request,
                response_cls,
                "UNAUTHENTICATED",
                "missing or invalid auth token",
                retryable=False,
            )
            return

        parsed_request = request_cls()
        try:
            parsed_request.ParseFromString(request.data)
        except DecodeError:
            await self._respond_error(
                request,
                response_cls,
                "INVALID_ARGUMENT",
                "invalid protobuf request",
                retryable=False,
            )
            return

        try:
            # The adapter port is synchronous and may block for seconds (network
            # round trips, slow backends). Every primary shares ONE event loop and
            # ONE connection (nats_runtime), so run the call on a worker thread:
            # inline it would stall every other endpoint of every service in the
            # process, plus nats-py's own PING/PONG handling.
            response = await asyncio.to_thread(call, parsed_request)
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"VectorStorePrimaryAdapterNATS: unexpected error handling {request.subject!r}"
            )
            await self._respond_error(
                request, response_cls, "INTERNAL", "internal error", retryable=True
            )
            return

        await respond_protobuf(request, response, response_cls)

    def _is_authenticated(self, request: Request) -> bool:
        headers = request.headers or {}
        token = headers.get(AUTH_HEADER)
        if not token:
            return False
        try:
            verify_service_token(token, self._jwt_secret)
        except InvalidServiceTokenError:
            return False
        return True

    @staticmethod
    async def _respond_error(
        request: Request,
        response_cls: Callable[..., Message],
        code: str,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        response = response_cls(
            error=common_pb2.CallError(code=code, message=message, retryable=retryable)
        )
        await respond_protobuf(request, response, response_cls)

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per IVectorStorePort method.
    # ------------------------------------------------------------------

    async def _handle_initialize(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.InitializeRequest,
            vector_store_pb2.InitializeResponse,
            self._call_initialize,
        )

    def _call_initialize(
        self, req: vector_store_pb2.InitializeRequest
    ) -> vector_store_pb2.InitializeResponse:
        self._adapter.initialize()
        return vector_store_pb2.InitializeResponse()

    async def _handle_create_collection(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.CreateCollectionRequest,
            vector_store_pb2.CreateCollectionResponse,
            self._call_create_collection,
        )

    def _call_create_collection(
        self, req: vector_store_pb2.CreateCollectionRequest
    ) -> vector_store_pb2.CreateCollectionResponse:
        self._adapter.create_collection(
            req.collection_name, req.dimension, req.distance_metric
        )
        return vector_store_pb2.CreateCollectionResponse()

    async def _handle_delete_collection(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.DeleteCollectionRequest,
            vector_store_pb2.DeleteCollectionResponse,
            self._call_delete_collection,
        )

    def _call_delete_collection(
        self, req: vector_store_pb2.DeleteCollectionRequest
    ) -> vector_store_pb2.DeleteCollectionResponse:
        self._adapter.delete_collection(req.collection_name)
        return vector_store_pb2.DeleteCollectionResponse()

    async def _handle_list_collections(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.ListCollectionsRequest,
            vector_store_pb2.ListCollectionsResponse,
            self._call_list_collections,
        )

    def _call_list_collections(
        self, req: vector_store_pb2.ListCollectionsRequest
    ) -> vector_store_pb2.ListCollectionsResponse:
        names = self._adapter.list_collections()
        return vector_store_pb2.ListCollectionsResponse(
            collections=vector_store_pb2.CollectionNames(names=names)
        )

    async def _handle_store_vectors(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.StoreVectorsRequest,
            vector_store_pb2.StoreVectorsResponse,
            self._call_store_vectors,
        )

    def _call_store_vectors(
        self, req: vector_store_pb2.StoreVectorsRequest
    ) -> vector_store_pb2.StoreVectorsResponse:
        documents = [
            VectorDocument(
                id=doc.id,
                vector=_pb_to_vector(doc.vector)
                if doc.HasField("vector")
                else np.array([]),
                metadata=dict(doc.metadata),
                payload=dict(doc.payload) if doc.HasField("payload") else None,
            )
            for doc in req.documents
        ]
        self._adapter.store_vectors(req.collection_name, documents)
        return vector_store_pb2.StoreVectorsResponse()

    async def _handle_search(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.SearchRequest,
            vector_store_pb2.SearchResponse,
            self._call_search,
        )

    def _call_search(
        self, req: vector_store_pb2.SearchRequest
    ) -> vector_store_pb2.SearchResponse:
        query_vector = np.array(list(req.query_vector), dtype=np.float32)
        results = self._adapter.search(
            req.collection_name,
            query_vector,
            k=req.k,
            filter=dict(req.filter) if req.HasField("filter") else None,
            include_vectors=req.include_vectors,
            include_metadata=req.include_metadata,
        )
        return vector_store_pb2.SearchResponse(
            results=vector_store_pb2.SearchResultList(
                results=[_search_result_to_pb(result) for result in results]
            )
        )

    async def _handle_get_vector(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.GetVectorRequest,
            vector_store_pb2.GetVectorResponse,
            self._call_get_vector,
        )

    def _call_get_vector(
        self, req: vector_store_pb2.GetVectorRequest
    ) -> vector_store_pb2.GetVectorResponse:
        document = self._adapter.get_vector(
            req.collection_name, req.vector_id, req.include_vector
        )
        return vector_store_pb2.GetVectorResponse(
            found=vector_store_pb2.VectorDocumentOrNone(
                document=_document_to_pb(document) if document is not None else None
            )
        )

    async def _handle_update_vector(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.UpdateVectorRequest,
            vector_store_pb2.UpdateVectorResponse,
            self._call_update_vector,
        )

    def _call_update_vector(
        self, req: vector_store_pb2.UpdateVectorRequest
    ) -> vector_store_pb2.UpdateVectorResponse:
        self._adapter.update_vector(
            req.collection_name,
            req.vector_id,
            vector=_pb_to_vector(req.vector) if req.HasField("vector") else None,
            metadata=dict(req.metadata) if req.HasField("metadata") else None,
            payload=dict(req.payload) if req.HasField("payload") else None,
        )
        return vector_store_pb2.UpdateVectorResponse()

    async def _handle_delete_vectors(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.DeleteVectorsRequest,
            vector_store_pb2.DeleteVectorsResponse,
            self._call_delete_vectors,
        )

    def _call_delete_vectors(
        self, req: vector_store_pb2.DeleteVectorsRequest
    ) -> vector_store_pb2.DeleteVectorsResponse:
        self._adapter.delete_vectors(req.collection_name, list(req.vector_ids))
        return vector_store_pb2.DeleteVectorsResponse()

    async def _handle_count_vectors(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.CountVectorsRequest,
            vector_store_pb2.CountVectorsResponse,
            self._call_count_vectors,
        )

    def _call_count_vectors(
        self, req: vector_store_pb2.CountVectorsRequest
    ) -> vector_store_pb2.CountVectorsResponse:
        count = self._adapter.count_vectors(req.collection_name)
        return vector_store_pb2.CountVectorsResponse(count=count)

    async def _handle_close(self, request: Request) -> None:
        await self._handle(
            request,
            vector_store_pb2.CloseRequest,
            vector_store_pb2.CloseResponse,
            self._call_close,
        )

    def _call_close(
        self, req: vector_store_pb2.CloseRequest
    ) -> vector_store_pb2.CloseResponse:
        self._adapter.close()
        return vector_store_pb2.CloseResponse()
