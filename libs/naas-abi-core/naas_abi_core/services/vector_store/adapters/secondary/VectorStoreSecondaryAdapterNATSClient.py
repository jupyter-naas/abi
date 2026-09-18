"""NATS RPC client adapter for the vector_store kernel domain.

Implements ``IVectorStorePort`` by calling out to a remote
``VectorStorePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/vector_store/v1/vector_store.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there.

``nats-py`` has no synchronous client, so -- like
``ObjectStorageSecondaryAdapterNATSClient`` and
``naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter`` --
this adapter bridges async NATS onto the synchronous port with ONE
persistent background thread running its own asyncio event loop (started
lazily on first use) and a single NATS connection reused across calls. Every
synchronous port method submits its async request via
``asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)`` and
blocks until it completes or raises, retrying once on a stale connection --
same shape as ``NATSJetStreamAdapter.publish``.

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

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import RLock, Thread
from typing import Any, Self, TypeVar

import nats
import numpy as np
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import DEFAULT_TTL, issue_service_token
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
from nats.aio.client import Client as NATSClient

_DEFAULT_TIMEOUT_SECONDS = 10.0
# Reissue the token this long before it actually expires, so a call that's
# in flight while the token is borderline doesn't get rejected mid-request.
_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)

_ResponseT = TypeVar("_ResponseT", bound=Message)


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


class VectorStoreSecondaryAdapterNATSClient(IVectorStorePort):
    """Calls a remote ``VectorStorePrimaryAdapterNATS`` over NATS RPC."""

    def __init__(
        self,
        nats_url: str,
        jwt_secret: str,
        service_identity: str,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._nats_url = nats_url
        self._jwt_secret = jwt_secret
        self._service_identity = service_identity
        self._timeout_seconds = timeout_seconds

        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: Thread | None = None
        self._nc: NATSClient | None = None
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        # Guards connect/reconnect + token bookkeeping on the persistent
        # loop, mirroring NATSJetStreamAdapter.__publish_lock.
        self._call_lock = RLock()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self) -> None:
        """Implements ``IVectorStorePort.close()`` by releasing this
        client's own NATS connection and background loop -- deliberately
        NOT by invoking the remote ``close`` RPC endpoint.

        This is a judgment call, not a literal 1:1 mapping: for every other
        concrete ``IVectorStorePort`` adapter (Qdrant, QdrantInMemory,
        SqliteVec), ``close()`` means "release *my* exclusive connection to
        the store" -- each owns one. A NATS RPC client has no such exclusive
        ownership: ``VectorStorePrimaryAdapterNATS`` wraps one raw adapter
        shared across every concurrent caller on the subject, so forwarding
        this call over the wire would tear that shared adapter's connection
        down out from under every other in-flight and future caller --
        exactly backwards from what one caller closing its own handle
        should do. The ``close`` RPC endpoint still exists server-side
        (``VectorStorePrimaryAdapterNATS._call_close``/``_handle_close``,
        kept for 1:1 completeness with the port and for whatever process
        genuinely owns that shared adapter's lifecycle), this client simply
        never calls it itself -- it only tears down what it itself opened.
        """
        with self._call_lock:
            self._close_connection()
            self._stop_loop()

    # ------------------------------------------------------------------
    # Persistent background event loop, same shape as
    # ObjectStorageSecondaryAdapterNATSClient / NATSJetStreamAdapter.
    # ------------------------------------------------------------------

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None and self._loop.is_running():
            return self._loop

        ready = ThreadingEvent()
        holder: dict[str, asyncio.AbstractEventLoop] = {}

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            holder["loop"] = loop
            ready.set()
            loop.run_forever()
            loop.close()

        thread = Thread(
            target=_run,
            daemon=True,
            name="vector-store-nats-client-loop",
        )
        thread.start()
        ready.wait()
        self._loop = holder["loop"]
        self._loop_thread = thread
        return self._loop

    def _run_coro(self, coro, timeout: float | None = None):
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout or self._timeout_seconds)

    def _stop_loop(self) -> None:
        loop = self._loop
        thread = self._loop_thread
        self._loop = None
        self._loop_thread = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5.0)

    async def _ensure_connection_async(self) -> NATSClient:
        if self._nc is not None and self._nc.is_connected:
            return self._nc
        nc = await nats.connect(self._nats_url)
        self._nc = nc
        return nc

    def _close_connection(self) -> None:
        nc = self._nc
        self._nc = None
        if nc is not None and self._loop is not None and self._loop.is_running():
            try:
                self._run_coro(nc.close(), timeout=5.0)
            except Exception:  # noqa: BLE001
                # Best-effort close of a connection we're discarding anyway
                # (already stale, or being replaced by a fresh reconnect).
                logger.opt(exception=True).debug(
                    "VectorStoreSecondaryAdapterNATSClient: error closing stale connection"
                )

    # ------------------------------------------------------------------
    # Auth: issue once, reissue only when close to expiry.
    # ------------------------------------------------------------------

    def _current_token(self) -> str:
        now = datetime.now(UTC)
        if (
            self._token is None
            or self._token_expires_at is None
            or now >= self._token_expires_at - _TOKEN_RENEWAL_MARGIN
        ):
            self._token = issue_service_token(self._service_identity, self._jwt_secret)
            self._token_expires_at = now + DEFAULT_TTL
        return self._token

    # ------------------------------------------------------------------
    # RPC plumbing.
    # ------------------------------------------------------------------

    def _context(self) -> common_pb2.CallContext:
        return common_pb2.CallContext(
            trace_id=str(uuid.uuid4()),
            timeout_ms=int(self._timeout_seconds * 1000),
        )

    def _call(
        self, subject: str, request: Message, response_cls: type[_ResponseT]
    ) -> _ResponseT:
        payload = request.SerializeToString()
        with self._call_lock:
            headers = {AUTH_HEADER: self._current_token()}
            try:
                msg = self._run_coro(self._do_request_async(subject, payload, headers))
            except Exception:  # noqa: BLE001
                self._close_connection()
                try:
                    msg = self._run_coro(
                        self._do_request_async(subject, payload, headers)
                    )
                except Exception as exc:
                    self._close_connection()
                    raise ConnectionError(
                        f"vector_store NATS RPC to {subject!r} failed"
                    ) from exc

        response = response_cls()
        response.ParseFromString(msg.data)
        return response

    async def _do_request_async(self, subject: str, payload: bytes, headers: dict[str, str]):
        nc = await self._ensure_connection_async()
        return await nc.request(
            subject, payload, timeout=self._timeout_seconds, headers=headers
        )

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
