"""NATS RPC client adapter for the triple_store kernel domain.

Implements ``ITripleStorePort`` by calling out to a remote
``TripleStorePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/triple_store/v1/triple_store.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
by the transport after failure; a timeout may hide a completed operation.

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

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TypeVar, cast

import rdflib
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.triple_store.v1 import triple_store_pb2
from naas_abi_core.services.triple_store.adapters.triple_store_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
    TRANSFER_PREFIX,
)
from naas_abi_core.services.triple_store.adapters.triple_store_stream_codec import (
    decode_header,
    decode_rows,
    decode_triples,
)
from naas_abi_core.services.triple_store.TripleStorePorts import (
    Exceptions,
    ITripleStorePort,
    OntologyEvent,
    QueryStream,
    Triple,
)
from naas_abi_proto.transfer.v1 import transfer_pb2 as transfer_pb
from naas_abi_sdk.telemetry import TransferTrace, transfer_span
from naas_abi_sdk.transfer import transfer_subject
from nats.errors import NoRespondersError
from rdflib import Graph, URIRef, Variable
from rdflib.term import Identifier
from rdflib.util import from_n3

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
                status_code=detail.status_code
                if detail.HasField("status_code")
                else None,
                response_body=detail.response_body
                if detail.HasField("response_body")
                else None,
                endpoint=detail.endpoint if detail.HasField("endpoint") else None,
                attempts=detail.attempts if detail.HasField("attempts") else None,
            )
        raise Exceptions.RequestError(operation="unknown", message=error.message)
    raise RuntimeError(f"triple_store NATS RPC failed ({error.code}): {error.message}")


_TransferReply = TypeVar("_TransferReply", bound=Message)


class TripleStoreSecondaryAdapterNATSClient(NatsRPCClient, ITripleStorePort):
    """Calls a remote ``TripleStorePrimaryAdapterNATS`` over NATS RPC."""

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

    # ------------------------------------------------------------------
    # Streamed reads over transfer frames (triple_store_stream_codec.py,
    # docs/adr/20261003_nats-streamed-results.md). Frames are fetched as the
    # caller iterates; leaving the ``with`` closes the session.
    # ------------------------------------------------------------------

    @contextmanager
    def query_stream(self, query: str) -> Iterator[QueryStream]:
        metadata = triple_store_pb2.QueryRequest(query=query).SerializeToString()
        with self._stream("query", metadata) as frames:
            if frames is None:  # an engine without the transfer endpoint
                yield QueryStream.from_result(self.query(query))
                return
            header = next(frames, None)
            if header is None:
                raise RuntimeError("triple_store stream ended without its header")
            result = decode_header(header)
            if result.result_type == "SELECT":
                result.rows = (row for frame in frames for row in decode_rows(frame))
            elif result.result_type in ("CONSTRUCT", "DESCRIBE"):
                bnodes: dict = {}
                result.triples = (
                    triple
                    for frame in frames
                    for triple in decode_triples(frame, bnodes)
                )
            yield result

    @contextmanager
    def export(self, graph_name: URIRef | None = None) -> Iterator[Iterator[Triple]]:
        metadata = str(graph_name).encode("utf-8") if graph_name is not None else b""
        with self._stream("export", metadata) as frames:
            if frames is None:
                with super().export(graph_name) as triples:
                    yield triples
                return
            bnodes: dict = {}
            yield (
                triple for frame in frames for triple in decode_triples(frame, bnodes)
            )

    @contextmanager
    def _stream(
        self, operation: str, metadata: bytes
    ) -> Iterator[Iterator[bytes] | None]:
        # One span for the whole stream (totals as attributes), not one per frame.
        with transfer_span(TRANSFER_PREFIX, operation) as trace:
            nc = self._run_coro(self._ensure_connection_async())
            try:
                opened = self._transfer_call(
                    transfer_pb.OpenRequest(
                        operation=operation,
                        metadata=metadata,
                        chunk_bytes=min(1024 * 1024, nc.max_payload // 2),
                    ),
                    transfer_pb.OpenResponse,
                    trace,
                )
            except NoRespondersError:
                yield None
                return
            try:
                self._transfer_call(
                    transfer_pb.StartRequest(id=opened.id),
                    transfer_pb.StartResponse,
                    trace,
                )
                yield self._frames(opened.id, trace)
            finally:
                try:
                    self._transfer_call(
                        transfer_pb.CloseRequest(id=opened.id),
                        transfer_pb.CloseResponse,
                        trace,
                    )
                except Exception as exc:  # noqa: BLE001 - idle expiry releases it
                    logger.warning("Stream cleanup failed: {}", type(exc).__name__)

    def _frames(self, transfer_id: str, trace: TransferTrace) -> Iterator[bytes]:
        sequence, frame = 0, bytearray()
        while True:
            reply = self._transfer_call(
                transfer_pb.ReadRequest(id=transfer_id, sequence=sequence),
                transfer_pb.ReadResponse,
                trace,
            )
            if reply.sequence != sequence:
                raise RuntimeError("triple_store stream sequence mismatch")
            if reply.done:
                if frame:
                    raise RuntimeError("triple_store stream ended mid-frame")
                return
            if reply.pending:
                time.sleep(0.02)
                continue
            sequence += 1
            frame.extend(reply.data)
            if reply.frame_end:
                yield bytes(frame)
                frame.clear()

    def _transfer_call(
        self, request: Message, response_cls: type[_TransferReply], trace: TransferTrace
    ) -> _TransferReply:
        operation = type(request).__name__.removesuffix("Request").lower()
        request.context.CopyFrom(self._context())  # type: ignore[attr-defined]
        response = self._call(
            transfer_subject(TRANSFER_PREFIX, operation, getattr(request, "id", "")),
            request,
            response_cls,
            transfer=trace,
        )
        if response.HasField("error"):
            _raise_for_error(cast(Any, response).error, None)
        return response

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
