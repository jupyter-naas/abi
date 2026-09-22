"""NATS RPC primary adapter for the triple_store kernel domain.

Exposes a real ``ITripleStorePort`` (or the richer ``ITripleStoreService``
domain object) as a NATS micro-service (see
``naas_abi_core/proto/triple_store/v1/triple_store.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there). This
is the server side; the matching client is
``TripleStoreSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``triple_store_nats_contract`` below -- that's
a neutral module neither adapter owns, so this file and the client's don't
depend on each other; see that module's docstring for why).

Accepts either an ``ITripleStorePort`` (a bare secondary adapter, e.g. in
tests) or an ``ITripleStoreService`` (the real engine-loaded domain service,
``TripleStoreService``) -- deliberately, not for convenience: wrapping the
raw adapter instead of the domain service would silently skip
``TripleStoreService``'s event publishing (``TriplesInserted``/
``TriplesRemoved``/``GraphCreated``/``GraphCleared``/``GraphDropped``/
``TripleStoreError``) and its batched bus notification for every remote
caller landing on this node, which would only diverge from in-process
behaviour, not match it. ``EngineNATSLoader`` always passes the domain
service.

One caveat from that choice: ``handle_view_event`` is part of
``ITripleStorePort`` (every secondary adapter implements it) but is NOT part
of ``ITripleStoreService`` -- ``TripleStoreService`` never delegates to it at
all (grep the repo: nothing calls ``handle_view_event`` anywhere, on any
adapter, outside adapter definitions and their own tests). So when this
adapter is wired over the real domain service, its ``handle_view_event``
endpoint has nothing to call and answers ``NOT_SUPPORTED`` rather than
crashing or silently doing nothing; it only actually dispatches when
constructed directly over a raw ``ITripleStorePort`` (e.g. in tests).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

import nats
import nats.micro
import rdflib
from google.protobuf.message import DecodeError, Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_rpc import respond_protobuf
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.triple_store.v1 import triple_store_pb2
from naas_abi_core.services.triple_store.adapters.triple_store_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.triple_store.TripleStorePorts import (
    Exceptions,
    ITripleStorePort,
    ITripleStoreService,
    OntologyEvent,
)
from nats.micro.request import Request
from nats.micro.service import Service
from rdflib import Graph, URIRef

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "TripleStorePrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


class _OperationNotSupportedError(Exception):
    """Raised locally when the wrapped object doesn't expose an operation.

    Only ever raised for ``handle_view_event`` against an ``ITripleStoreService``
    -- see the module docstring.
    """


def _graph_to_nt(graph: Graph) -> bytes:
    data = graph.serialize(format="nt", encoding="utf-8")
    assert isinstance(data, bytes)
    return data


def _nt_to_graph(data: bytes) -> Graph:
    graph = Graph()
    if data:
        graph.parse(data=data, format="nt")
    return graph


def _graph_name_from_wire(graph_name: str) -> str | URIRef:
    """Reconstruct a ``graph_name: str | URIRef`` argument from its wire string.

    The wildcard sentinel ``"*"`` is kept as a plain ``str`` -- several
    ``ITripleStorePort`` adapters compare ``graph_name == "*"`` directly (e.g.
    ``TripleStoreService__SecondaryAdaptor__OxigraphEmbedded.get_subject_graph``),
    and ``URIRef("*") == "*"`` is actually ``False`` (rdflib's
    ``Identifier.__eq__`` requires the other side be a compatible Identifier
    too). Every other value becomes a real ``URIRef``.
    """
    if graph_name == "*":
        return "*"
    return URIRef(graph_name)


def _triple_pattern_from_pb(
    pb: triple_store_pb2.TriplePattern,
) -> tuple[URIRef | None, URIRef | None, URIRef | None]:
    return (
        URIRef(pb.subject) if pb.HasField("subject") else None,
        URIRef(pb.predicate) if pb.HasField("predicate") else None,
        URIRef(pb.object) if pb.HasField("object") else None,
    )


_EVENT_FROM_PB = {
    triple_store_pb2.ONTOLOGY_EVENT_TYPE_INSERT: OntologyEvent.INSERT,
    triple_store_pb2.ONTOLOGY_EVENT_TYPE_DELETE: OntologyEvent.DELETE,
}


def _query_result_to_pb(result: object) -> triple_store_pb2.QueryResult:
    """Normalize whatever ``query``/``query_view`` handed back into the wire shape.

    ``ITripleStorePort.query`` is typed as returning ``rdflib.query.Result``,
    but not every adapter actually conforms: HTTP-backed and embedded adapters
    sometimes hand back a bare ``rdflib.Graph`` (CONSTRUCT/DESCRIBE) or a bare
    ``bool`` (ASK) instead (see e.g. ``ApacheJenaTDB2.query``,
    ``TripleStoreService__SecondaryAdaptor__OxigraphEmbedded.query``). This
    adapter accepts all of those shapes so the wire contract stays correct
    regardless of which concrete adapter is behind it.
    """
    if isinstance(result, rdflib.query.Result):
        if result.type == "ASK":
            return triple_store_pb2.QueryResult(
                result_type="ASK", ask_answer=bool(result.askAnswer)
            )
        if result.type in ("CONSTRUCT", "DESCRIBE"):
            graph = result.graph if result.graph is not None else Graph()
            return triple_store_pb2.QueryResult(
                result_type=result.type,
                construct_triples_nt=_graph_to_nt(graph),
            )
        # SELECT
        var_names = [str(v) for v in (result.vars or [])]
        rows = []
        for row in result:
            assert isinstance(row, rdflib.query.ResultRow)
            bindings: dict[str, str] = {}
            for name in row.labels:
                term = row[name]
                if term is not None:
                    bindings[name] = term.n3()
            rows.append(triple_store_pb2.Row(bindings=bindings))
        return triple_store_pb2.QueryResult(
            result_type="SELECT",
            select=triple_store_pb2.SelectResult(vars=var_names, rows=rows),
        )
    if isinstance(result, Graph):
        return triple_store_pb2.QueryResult(
            result_type="CONSTRUCT",
            construct_triples_nt=_graph_to_nt(result),
        )
    if isinstance(result, bool):
        return triple_store_pb2.QueryResult(result_type="ASK", ask_answer=result)
    raise TypeError(f"Unsupported query() result type: {type(result)!r}")


class TripleStorePrimaryAdapterNATS:
    """Serves triple_store over NATS RPC (request/reply).

    Wraps a real ``ITripleStorePort`` adapter *or* the domain service
    (``ITripleStoreService``) and registers one NATS micro-service endpoint
    per ``ITripleStorePort`` method. Each endpoint authenticates the caller
    via ``Nats-Auth-Token`` before doing anything else, then decodes the
    Protobuf request, calls straight through to the wrapped object, and
    encodes a Protobuf response. Errors -- auth failures, known domain
    exceptions, anything unexpected -- are always reported as a normal
    response carrying a populated ``CallError``, never as a crashed handler
    or a raw NATS-level error.
    """

    def __init__(
        self,
        adapter: ITripleStorePort | ITripleStoreService,
        jwt_secret: str,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``triple_store`` NATS service on ``nc``.

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
            description="ABI kernel triple_store domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="insert",
            subject=f"{SUBJECT_PREFIX}.insert",
            handler=self._handle_insert,
        )
        await service.add_endpoint(
            name="remove",
            subject=f"{SUBJECT_PREFIX}.remove",
            handler=self._handle_remove,
        )
        await service.add_endpoint(
            name="get",
            subject=f"{SUBJECT_PREFIX}.get",
            handler=self._handle_get,
        )
        await service.add_endpoint(
            name="handle_view_event",
            subject=f"{SUBJECT_PREFIX}.handle_view_event",
            handler=self._handle_handle_view_event,
        )
        await service.add_endpoint(
            name="query",
            subject=f"{SUBJECT_PREFIX}.query",
            handler=self._handle_query,
        )
        await service.add_endpoint(
            name="query_view",
            subject=f"{SUBJECT_PREFIX}.query_view",
            handler=self._handle_query_view,
        )
        await service.add_endpoint(
            name="get_subject_graph",
            subject=f"{SUBJECT_PREFIX}.get_subject_graph",
            handler=self._handle_get_subject_graph,
        )
        await service.add_endpoint(
            name="create_graph",
            subject=f"{SUBJECT_PREFIX}.create_graph",
            handler=self._handle_create_graph,
        )
        await service.add_endpoint(
            name="clear_graph",
            subject=f"{SUBJECT_PREFIX}.clear_graph",
            handler=self._handle_clear_graph,
        )
        await service.add_endpoint(
            name="drop_graph",
            subject=f"{SUBJECT_PREFIX}.drop_graph",
            handler=self._handle_drop_graph,
        )
        await service.add_endpoint(
            name="list_graphs",
            subject=f"{SUBJECT_PREFIX}.list_graphs",
            handler=self._handle_list_graphs,
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
        except Exceptions.SubjectNotFoundError as exc:
            await self._respond_error(
                request, response_cls, "SUBJECT_NOT_FOUND", str(exc), retryable=False
            )
            return
        except Exceptions.SubscriptionNotFoundError as exc:
            await self._respond_error(
                request,
                response_cls,
                "SUBSCRIPTION_NOT_FOUND",
                str(exc),
                retryable=False,
            )
            return
        except Exceptions.ViewNotFoundError as exc:
            await self._respond_error(
                request, response_cls, "VIEW_NOT_FOUND", str(exc), retryable=False
            )
            return
        except Exceptions.GraphNotFoundError as exc:
            await self._respond_error(
                request, response_cls, "GRAPH_NOT_FOUND", str(exc), retryable=False
            )
            return
        except Exceptions.GraphAlreadyExistsError as exc:
            await self._respond_error(
                request,
                response_cls,
                "GRAPH_ALREADY_EXISTS",
                str(exc),
                retryable=False,
            )
            return
        except Exceptions.RequestError as exc:
            detail = triple_store_pb2.TripleStoreRequestErrorDetail(
                operation=exc.operation
            )
            if exc.status_code is not None:
                detail.status_code = exc.status_code
            if exc.response_body is not None:
                detail.response_body = exc.response_body
            if exc.endpoint is not None:
                detail.endpoint = exc.endpoint
            if exc.attempts is not None:
                detail.attempts = exc.attempts
            await self._respond_error(
                request,
                response_cls,
                "REQUEST_ERROR",
                str(exc),
                retryable=True,
                status=exc.status_code,
                detail=detail,
            )
            return
        except _OperationNotSupportedError as exc:
            await self._respond_error(
                request, response_cls, "NOT_SUPPORTED", str(exc), retryable=False
            )
            return
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"TripleStorePrimaryAdapterNATS: unexpected error handling {request.subject!r}"
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
        status: int | None = None,
        detail: triple_store_pb2.TripleStoreRequestErrorDetail | None = None,
    ) -> None:
        call_error = common_pb2.CallError(
            code=code, message=message, retryable=retryable
        )
        if status is not None:
            call_error.status = status
        kwargs: dict[str, Message] = {"error": call_error}
        if detail is not None:
            kwargs["error_detail"] = detail
        response = response_cls(**kwargs)
        await respond_protobuf(request, response, response_cls)

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per ITripleStorePort method.
    # ------------------------------------------------------------------

    async def _handle_insert(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.InsertRequest,
            triple_store_pb2.InsertResponse,
            self._call_insert,
        )

    def _call_insert(
        self, req: triple_store_pb2.InsertRequest
    ) -> triple_store_pb2.InsertResponse:
        self._adapter.insert(_nt_to_graph(req.triples_nt), URIRef(req.graph_name))
        return triple_store_pb2.InsertResponse()

    async def _handle_remove(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.RemoveRequest,
            triple_store_pb2.RemoveResponse,
            self._call_remove,
        )

    def _call_remove(
        self, req: triple_store_pb2.RemoveRequest
    ) -> triple_store_pb2.RemoveResponse:
        self._adapter.remove(_nt_to_graph(req.triples_nt), URIRef(req.graph_name))
        return triple_store_pb2.RemoveResponse()

    async def _handle_get(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.GetRequest,
            triple_store_pb2.GetResponse,
            self._call_get,
        )

    def _call_get(
        self, req: triple_store_pb2.GetRequest
    ) -> triple_store_pb2.GetResponse:
        graph = self._adapter.get()
        return triple_store_pb2.GetResponse(triples_nt=_graph_to_nt(graph))

    async def _handle_handle_view_event(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.HandleViewEventRequest,
            triple_store_pb2.HandleViewEventResponse,
            self._call_handle_view_event,
        )

    def _call_handle_view_event(
        self, req: triple_store_pb2.HandleViewEventRequest
    ) -> triple_store_pb2.HandleViewEventResponse:
        handler = getattr(self._adapter, "handle_view_event", None)
        if handler is None:
            raise _OperationNotSupportedError(
                "handle_view_event is not exposed by the wrapped domain "
                "service (ITripleStoreService); it is only reachable when "
                "this primary adapter wraps a raw ITripleStorePort adapter."
            )
        event = _EVENT_FROM_PB.get(req.event)
        if event is None:
            raise ValueError(f"Unknown OntologyEventType: {req.event!r}")
        handler(
            view=_triple_pattern_from_pb(req.view),
            event=event,
            triple=_triple_pattern_from_pb(req.triple),
        )
        return triple_store_pb2.HandleViewEventResponse()

    async def _handle_query(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.QueryRequest,
            triple_store_pb2.QueryResponse,
            self._call_query,
        )

    def _call_query(
        self, req: triple_store_pb2.QueryRequest
    ) -> triple_store_pb2.QueryResponse:
        result = self._adapter.query(req.query)
        return triple_store_pb2.QueryResponse(success=_query_result_to_pb(result))

    async def _handle_query_view(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.QueryViewRequest,
            triple_store_pb2.QueryViewResponse,
            self._call_query_view,
        )

    def _call_query_view(
        self, req: triple_store_pb2.QueryViewRequest
    ) -> triple_store_pb2.QueryViewResponse:
        result = self._adapter.query_view(req.view, req.query)
        return triple_store_pb2.QueryViewResponse(success=_query_result_to_pb(result))

    async def _handle_get_subject_graph(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.GetSubjectGraphRequest,
            triple_store_pb2.GetSubjectGraphResponse,
            self._call_get_subject_graph,
        )

    def _call_get_subject_graph(
        self, req: triple_store_pb2.GetSubjectGraphRequest
    ) -> triple_store_pb2.GetSubjectGraphResponse:
        graph = self._adapter.get_subject_graph(
            URIRef(req.subject), _graph_name_from_wire(req.graph_name)
        )
        return triple_store_pb2.GetSubjectGraphResponse(triples_nt=_graph_to_nt(graph))

    async def _handle_create_graph(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.CreateGraphRequest,
            triple_store_pb2.CreateGraphResponse,
            self._call_create_graph,
        )

    def _call_create_graph(
        self, req: triple_store_pb2.CreateGraphRequest
    ) -> triple_store_pb2.CreateGraphResponse:
        self._adapter.create_graph(URIRef(req.graph_name))
        return triple_store_pb2.CreateGraphResponse()

    async def _handle_clear_graph(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.ClearGraphRequest,
            triple_store_pb2.ClearGraphResponse,
            self._call_clear_graph,
        )

    def _call_clear_graph(
        self, req: triple_store_pb2.ClearGraphRequest
    ) -> triple_store_pb2.ClearGraphResponse:
        self._adapter.clear_graph(URIRef(req.graph_name))
        return triple_store_pb2.ClearGraphResponse()

    async def _handle_drop_graph(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.DropGraphRequest,
            triple_store_pb2.DropGraphResponse,
            self._call_drop_graph,
        )

    def _call_drop_graph(
        self, req: triple_store_pb2.DropGraphRequest
    ) -> triple_store_pb2.DropGraphResponse:
        self._adapter.drop_graph(URIRef(req.graph_name))
        return triple_store_pb2.DropGraphResponse()

    async def _handle_list_graphs(self, request: Request) -> None:
        await self._handle(
            request,
            triple_store_pb2.ListGraphsRequest,
            triple_store_pb2.ListGraphsResponse,
            self._call_list_graphs,
        )

    def _call_list_graphs(
        self, req: triple_store_pb2.ListGraphsRequest
    ) -> triple_store_pb2.ListGraphsResponse:
        graph_names = self._adapter.list_graphs()
        return triple_store_pb2.ListGraphsResponse(
            graph_names=triple_store_pb2.GraphNames(
                graph_names=[str(g) for g in graph_names]
            )
        )
