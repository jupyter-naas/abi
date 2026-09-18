"""NATS RPC client adapter for the triple_store kernel domain.

Implements ``ITripleStorePort`` by calling out to a remote
``TripleStorePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/triple_store/v1/triple_store.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there.

``nats-py`` has no synchronous client, so -- like
``naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter`` and
``ObjectStorageSecondaryAdapterNATSClient`` -- this adapter bridges async NATS
onto the synchronous port with ONE persistent background thread running its
own asyncio event loop (started lazily on first use) and a single NATS
connection reused across calls. Every synchronous port method submits its
async request via
``asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)`` and
blocks until it completes or raises, retrying once on a stale connection --
same shape as ``NATSJetStreamAdapter.publish``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather than
on every call. ``TripleStorePrimaryAdapterNATS`` must read the token from
that exact header -- both sides read ``AUTH_HEADER`` from
``triple_store_nats_contract``, a neutral module neither adapter owns, so
this file never has to import from the primary adapter's module (or vice
versa) just to agree on a header name.

This adapter constructs this process's own instance of ``TripleStoreService``
via ``TripleStoreService(triple_store_adapter=nats_client)`` exactly like any
other secondary adapter (``oxigraph``, ``fs``, ...) -- it just happens to
forward every call over the wire instead of touching a store directly. See
the primary adapter's module docstring for why ``handle_view_event`` can
answer ``NOT_SUPPORTED`` depending on what the remote side wraps -- that's a
server-side decision this client has no control over, it just surfaces
whatever ``CallError.code`` comes back.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import RLock, Thread
from typing import Self, TypeVar

import nats
import rdflib
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import DEFAULT_TTL, issue_service_token
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.triple_store.v1 import triple_store_pb2
from naas_abi_core.services.triple_store.adapters.triple_store_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.triple_store.TripleStorePorts import (
    Exceptions,
    ITripleStorePort,
    OntologyEvent,
)
from nats.aio.client import Client as NATSClient
from rdflib import Graph, URIRef, Variable
from rdflib.term import Identifier
from rdflib.util import from_n3

_DEFAULT_TIMEOUT_SECONDS = 10.0
# Reissue the token this long before it actually expires, so a call that's in
# flight while the token is borderline doesn't get rejected mid-request.
_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)

_ResponseT = TypeVar("_ResponseT", bound=Message)

_EVENT_TO_PB = {
    OntologyEvent.INSERT: triple_store_pb2.ONTOLOGY_EVENT_TYPE_INSERT,
    OntologyEvent.DELETE: triple_store_pb2.ONTOLOGY_EVENT_TYPE_DELETE,
}


def _graph_to_nt(graph: Graph) -> bytes:
    data = graph.serialize(format="nt", encoding="utf-8")
    assert isinstance(data, bytes)
    return data


def _nt_to_graph(data: bytes) -> Graph:
    graph = Graph()
    if data:
        graph.parse(data=data, format="nt")
    return graph


def _triple_pattern_to_pb(
    pattern: tuple[URIRef | None, URIRef | None, URIRef | None],
) -> triple_store_pb2.TriplePattern:
    subject, predicate, obj = pattern
    kwargs: dict[str, str] = {}
    if subject is not None:
        kwargs["subject"] = str(subject)
    if predicate is not None:
        kwargs["predicate"] = str(predicate)
    if obj is not None:
        kwargs["object"] = str(obj)
    return triple_store_pb2.TriplePattern(**kwargs)


def _pb_to_query_result(pb: triple_store_pb2.QueryResult) -> rdflib.query.Result:
    """Reconstruct a real ``rdflib.query.Result`` from the wire shape.

    Deliberately a genuine ``rdflib.query.Result`` -- not a duck-typed
    stand-in -- so iterating a SELECT result yields real ``ResultRow``
    instances (several existing callers, e.g.
    ``naas_abi_core.utils.SPARQL`` and ``TripleStoreService`` itself, do
    ``assert isinstance(row, rdflib.query.ResultRow)``), and each bound
    value round-trips through ``rdflib.util.from_n3`` back into a properly
    typed ``URIRef``/``Literal``/``BNode`` -- see the ``.proto`` file's
    header comment for why that matters.
    """
    result = rdflib.query.Result(pb.result_type)
    if pb.result_type == "ASK":
        result.askAnswer = pb.ask_answer
    elif pb.result_type in ("CONSTRUCT", "DESCRIBE"):
        result.graph = _nt_to_graph(pb.construct_triples_nt)
    else:
        result.vars = [Variable(v) for v in pb.select.vars]
        result.bindings = [
            {
                Variable(name): _term_from_n3(value)
                for name, value in row.bindings.items()
            }
            for row in pb.select.rows
        ]
    return result


def _term_from_n3(value: str) -> Identifier:
    """Parse one wire-encoded N3 term back into a real rdflib term.

    ``rdflib.util.from_n3`` is typed as ``Node | str | None`` for the
    general case (it also accepts bare, non-N3 strings), but every value
    this client ever receives was written by the primary adapter via
    ``Term.n3()`` -- always a well-formed term -- so this narrows that back
    down to ``Identifier`` (the common base of URIRef/Literal/BNode) rather
    than propagating the wider type into every binding.
    """
    term = from_n3(value)
    if not isinstance(term, Identifier):
        raise TypeError(f"Unexpected non-term N3 value on the wire: {value!r}")
    return term


def _raise_for_error(
    error: common_pb2.CallError,
    detail: triple_store_pb2.TripleStoreRequestErrorDetail | None,
) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``TripleStorePrimaryAdapterNATS``
    encodes errors -- the generic adapter contract test asserts on the real
    exception types, not on the wire code.
    """
    if error.code == "SUBJECT_NOT_FOUND":
        raise Exceptions.SubjectNotFoundError(error.message)
    if error.code == "SUBSCRIPTION_NOT_FOUND":
        raise Exceptions.SubscriptionNotFoundError(error.message)
    if error.code == "VIEW_NOT_FOUND":
        raise Exceptions.ViewNotFoundError(error.message)
    if error.code == "GRAPH_NOT_FOUND":
        raise Exceptions.GraphNotFoundError(error.message)
    if error.code == "GRAPH_ALREADY_EXISTS":
        raise Exceptions.GraphAlreadyExistsError(error.message)
    if error.code == "REQUEST_ERROR":
        if detail is not None:
            raise Exceptions.RequestError(
                operation=detail.operation,
                message=error.message,
                status_code=detail.status_code if detail.HasField("status_code") else None,
                response_body=detail.response_body if detail.HasField("response_body") else None,
                endpoint=detail.endpoint if detail.HasField("endpoint") else None,
                attempts=detail.attempts if detail.HasField("attempts") else None,
            )
        raise Exceptions.RequestError(operation="unknown", message=error.message)
    raise RuntimeError(f"triple_store NATS RPC failed ({error.code}): {error.message}")


class TripleStoreSecondaryAdapterNATSClient(ITripleStorePort):
    """Calls a remote ``TripleStorePrimaryAdapterNATS`` over NATS RPC."""

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
        with self._call_lock:
            self._close_connection()
            self._stop_loop()

    # ------------------------------------------------------------------
    # Persistent background event loop, same shape as NATSJetStreamAdapter.
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
            name="triple-store-nats-client-loop",
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
                    "TripleStoreSecondaryAdapterNATSClient: error closing stale connection"
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
                        f"triple_store NATS RPC to {subject!r} failed"
                    ) from exc

        response = response_cls()
        response.ParseFromString(msg.data)
        return response

    async def _do_request_async(self, subject: str, payload: bytes, headers: dict[str, str]):
        nc = await self._ensure_connection_async()
        return await nc.request(
            subject, payload, timeout=self._timeout_seconds, headers=headers
        )

    @staticmethod
    def _detail_or_none(
        response: Message,
    ) -> triple_store_pb2.TripleStoreRequestErrorDetail | None:
        if response.HasField("error_detail"):  # type: ignore[attr-defined]
            return response.error_detail  # type: ignore[attr-defined,no-any-return]
        return None

    # ------------------------------------------------------------------
    # ITripleStorePort.
    # ------------------------------------------------------------------

    def insert(self, triples: Graph, graph_name: URIRef) -> None:
        request = triple_store_pb2.InsertRequest(
            context=self._context(),
            triples_nt=_graph_to_nt(triples),
            graph_name=str(graph_name),
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.insert", request, triple_store_pb2.InsertResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))

    def remove(self, triples: Graph, graph_name: URIRef) -> None:
        request = triple_store_pb2.RemoveRequest(
            context=self._context(),
            triples_nt=_graph_to_nt(triples),
            graph_name=str(graph_name),
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.remove", request, triple_store_pb2.RemoveResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))

    def get(self) -> Graph:
        request = triple_store_pb2.GetRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.get", request, triple_store_pb2.GetResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))
        return _nt_to_graph(response.triples_nt)

    def handle_view_event(
        self,
        view: tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: tuple[URIRef | None, URIRef | None, URIRef | None],
    ) -> None:
        request = triple_store_pb2.HandleViewEventRequest(
            context=self._context(),
            view=_triple_pattern_to_pb(view),
            event=_EVENT_TO_PB[event],
            triple=_triple_pattern_to_pb(triple),
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.handle_view_event",
            request,
            triple_store_pb2.HandleViewEventResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))

    def query(self, query: str) -> rdflib.query.Result:
        request = triple_store_pb2.QueryRequest(context=self._context(), query=query)
        response = self._call(
            f"{SUBJECT_PREFIX}.query", request, triple_store_pb2.QueryResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))
        return _pb_to_query_result(response.success)

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        request = triple_store_pb2.QueryViewRequest(
            context=self._context(), view=view, query=query
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.query_view", request, triple_store_pb2.QueryViewResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))
        return _pb_to_query_result(response.success)

    def get_subject_graph(self, subject: URIRef, graph_name: str | URIRef) -> Graph:
        request = triple_store_pb2.GetSubjectGraphRequest(
            context=self._context(),
            subject=str(subject),
            graph_name=str(graph_name),
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_subject_graph",
            request,
            triple_store_pb2.GetSubjectGraphResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))
        return _nt_to_graph(response.triples_nt)

    def create_graph(self, graph_name: URIRef) -> None:
        request = triple_store_pb2.CreateGraphRequest(
            context=self._context(), graph_name=str(graph_name)
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.create_graph",
            request,
            triple_store_pb2.CreateGraphResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))

    def clear_graph(self, graph_name: URIRef) -> None:
        request = triple_store_pb2.ClearGraphRequest(
            context=self._context(), graph_name=str(graph_name)
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.clear_graph",
            request,
            triple_store_pb2.ClearGraphResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))

    def drop_graph(self, graph_name: URIRef) -> None:
        request = triple_store_pb2.DropGraphRequest(
            context=self._context(), graph_name=str(graph_name)
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.drop_graph", request, triple_store_pb2.DropGraphResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))

    def list_graphs(self) -> list[URIRef]:
        request = triple_store_pb2.ListGraphsRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.list_graphs",
            request,
            triple_store_pb2.ListGraphsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error, self._detail_or_none(response))
        return [URIRef(g) for g in response.graph_names.graph_names]
