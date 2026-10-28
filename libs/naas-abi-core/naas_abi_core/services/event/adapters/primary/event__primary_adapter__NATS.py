"""NATS RPC primary adapter for the event kernel domain.

Exposes the ``EventService`` durable log as a NATS micro-service (see
``naas_abi_core/proto/event/v1/event.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there). This is the
server side; the matching client is ``EventSecondaryAdapterNATSClient``.

Auth (see ``naas_abi_core.engine.nats_auth``): every incoming request
must carry an engine token, verified against the JWKS, in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``event_nats_contract`` below -- that's a
neutral module neither adapter owns, so this file and the client's don't
depend on each other; see that module's docstring for why).

Scope note: the wire contract is the durable-log port's (``IEventAdapter``):
a remote ``EventService`` backed by ``EventSecondaryAdapterNATSClient``
serializes, stamps and broadcasts its own events, and only stores them here.
Every endpoint still goes through this engine's ``EventService`` -- its
stored-level operations (``append_stored``, ``query_stored``, ``max_seq``,
cursors) -- so a check in the domain service covers remote callers too. None
of them broadcasts: the publisher already did, so each event goes out once.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from functools import partial
from typing import Any, TypeVar

import nats
import nats.micro
from google.protobuf import struct_pb2
from google.protobuf.message import DecodeError, Message
from nats.micro.request import Request

from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import TokenVerifier
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import (
    RequestPayloadError,
    authenticate_request,
    request_payload,
    respond_protobuf,
)
from naas_abi_core.engine.nats_tracing import TracedService, add_traced_service
from naas_abi_core.engine.nats_transfer import (
    ServiceWithTransfers,
    TransferHost,
    thread_frames,
)
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.event.v1 import event_pb2
from naas_abi_core.services.event.adapters.event_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
    TRANSFER_PREFIX,
)
from naas_abi_core.services.event.adapters.event_stream_codec import (
    event_frames,
    event_to_pb,
)
from naas_abi_core.services.event.EventFilter import FilterError
from naas_abi_core.services.event.EventPort import (
    EventNotFoundError,
    EventTypeSummary,
    IEventAdapter,
    IEventService,
    InvalidEventError,
)
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.iam.guard import authorization_error_code
from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "EventPrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


def _type_to_pb(summary: EventTypeSummary) -> event_pb2.EventTypeSummary:
    return event_pb2.EventTypeSummary(
        event_type=summary.event_type,
        count=summary.count,
        last_seq=summary.last_seq,
        last_timestamp=summary.last_timestamp,
    )


# mypy --follow-untyped-imports can't resolve google.protobuf's
# dynamically-generated Struct class through its stub package -- same known
# upstream quirk as the Timestamp one documented in pyproject.toml's
# `[[tool.mypy.overrides]] module = "naas_abi_core.proto.*"`, just triggered
# here because this hand-written code names the well-known type directly.
def _struct_to_json_filter(
    has_field: bool,
    struct: struct_pb2.Struct,  # type: ignore[name-defined]
) -> dict | None:
    """Decode an optional wire ``Struct`` into the plain ``dict`` (or
    ``None``) ``IEventAdapter`` methods expect.

    Uses ``json_format.MessageToDict`` rather than ``dict(struct)`` --
    ``Struct``'s own ``Mapping`` mixin only converts the top level, leaving
    nested ``ListValue``/``Struct`` values un-decoded; ``MessageToDict``
    recurses all the way down to plain ``dict``/``list``/``str``/``float``/
    ``bool``/``None``.
    """
    if not has_field:
        return None
    from google.protobuf import json_format

    return json_format.MessageToDict(struct)


def _query_arguments(req: event_pb2.QueryRequest) -> dict[str, Any]:
    """``EventService.query_stored`` arguments from a wire ``QueryRequest``."""
    return {
        "event_type": req.event_type if req.HasField("event_type") else None,
        "since_seq": req.since_seq if req.HasField("since_seq") else None,
        "until_seq": req.until_seq if req.HasField("until_seq") else None,
        "since_timestamp": (
            req.since_timestamp if req.HasField("since_timestamp") else None
        ),
        "until_timestamp": (
            req.until_timestamp if req.HasField("until_timestamp") else None
        ),
        "filter": _struct_to_json_filter(req.HasField("json_filter"), req.json_filter),
        "limit": req.limit if req.HasField("limit") else None,
        "newest_first": req.newest_first,
        "search": req.search if req.HasField("search") else None,
    }


class EventPrimaryAdapterNATS(ServiceWithTransfers):
    """Serves the event durable log over NATS RPC (request/reply).

    Wraps the domain ``EventService`` and registers one NATS micro-service
    endpoint per durable-log operation. Each endpoint authenticates the
    caller via ``Nats-Auth-Token`` before doing anything else, then decodes
    the Protobuf request, calls the service as that caller (its
    ``CallContext``), and encodes a Protobuf response. Errors -- auth
    failures, unexpected exceptions -- are always reported as a normal
    response carrying a populated ``CallError``, never as a crashed handler
    or a raw NATS-level error.
    """

    def __init__(
        self, service: IEventService | IEventAdapter, verifier: TokenVerifier
    ) -> None:
        # A bare log (tests) is served through an EventService of its own.
        self._adapter = (
            service if isinstance(service, IEventService) else EventService(service)
        )
        self._verifier = verifier
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._service: TracedService | None = None
        # Streamed queries.
        self._transfer = TransferHost(
            TRANSFER_PREFIX,
            verifier,
            self._transfer_frames,
            operations=("query",),
            chunk_bytes=1024 * 1024,
            error_mapper=self._transfer_error,
        )

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``event`` NATS service on ``nc``.

        ``nc`` must already be connected -- this adapter never manages the
        connection lifecycle itself, only the service/endpoints layered on
        top of it. Calling this more than once is a no-op.
        """
        if self._service is not None:
            return

        service = await add_traced_service(
            nc,
            name=SERVICE_NAME,
            version=SERVICE_VERSION,
            description="ABI kernel event domain durable log, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="append",
            subject=f"{SUBJECT_PREFIX}.append",
            handler=self._handle_append,
        )
        await service.add_endpoint(
            name="query",
            subject=f"{SUBJECT_PREFIX}.query",
            handler=self._handle_query,
        )
        await service.add_endpoint(
            name="max_seq",
            subject=f"{SUBJECT_PREFIX}.max_seq",
            handler=self._handle_max_seq,
        )
        await service.add_endpoint(
            name="get_cursor",
            subject=f"{SUBJECT_PREFIX}.get_cursor",
            handler=self._handle_get_cursor,
        )
        await service.add_endpoint(
            name="set_cursor",
            subject=f"{SUBJECT_PREFIX}.set_cursor",
            handler=self._handle_set_cursor,
        )
        await service.add_endpoint(
            name="query_for_consumer",
            subject=f"{SUBJECT_PREFIX}.query_for_consumer",
            handler=self._handle_query_for_consumer,
        )
        await service.add_endpoint(
            name="list_event_types",
            subject=f"{SUBJECT_PREFIX}.list_event_types",
            handler=self._handle_list_event_types,
        )
        self._service = service
        await self._transfer.start(nc)

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
        caller = await authenticate_request(request, self._verifier, response_cls)
        if caller is None:
            return

        parsed_request = request_cls()
        try:
            parsed_request.ParseFromString(await request_payload(request))
        except RequestPayloadError as exc:
            await self._respond_error(
                request, response_cls, exc.code, exc.message, retryable=False
            )
            return
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
            response = await self._dispatch.call(call, parsed_request, caller)
        except (PermissionDeniedError, ResourceNotFoundError) as exc:
            await self._respond_error(
                request,
                response_cls,
                authorization_error_code(exc) or "PERMISSION_DENIED",
                str(exc),
                retryable=False,
            )
            return
        except EventNotFoundError as exc:
            await self._respond_error(
                request, response_cls, "EVENT_NOT_FOUND", str(exc), retryable=False
            )
            return
        except InvalidEventError as exc:
            await self._respond_error(
                request, response_cls, "INVALID_EVENT", str(exc), retryable=False
            )
            return
        except FilterError as exc:
            await self._respond_error(
                request, response_cls, "INVALID_FILTER", str(exc), retryable=False
            )
            return
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"EventPrimaryAdapterNATS: unexpected error handling {request.subject!r}"
            )
            await self._respond_error(
                request, response_cls, "INTERNAL", "internal error", retryable=True
            )
            return

        await respond_protobuf(request, response, response_cls)

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
    # Endpoint handlers -- one per durable-log operation.
    # ------------------------------------------------------------------

    async def _handle_append(self, request: Request) -> None:
        await self._handle(
            request,
            event_pb2.AppendRequest,
            event_pb2.AppendResponse,
            self._call_append,
        )

    def _call_append(self, req: event_pb2.AppendRequest) -> event_pb2.AppendResponse:
        stored = self._adapter.append_stored(
            event_id=req.event_id,
            event_type=req.event_type,
            timestamp=req.timestamp,
            payload=req.payload,
        )
        return event_pb2.AppendResponse(event=event_to_pb(stored))

    async def _handle_query(self, request: Request) -> None:
        await self._handle(
            request,
            event_pb2.QueryRequest,
            event_pb2.QueryResponse,
            self._call_query,
        )

    def _call_query(self, req: event_pb2.QueryRequest) -> event_pb2.QueryResponse:
        rows = self._adapter.query_stored(**_query_arguments(req))
        return event_pb2.QueryResponse(
            events=event_pb2.StoredEvents(events=[event_to_pb(row) for row in rows])
        )

    # ------------------------------------------------------------------
    # Streamed queries: one transfer session per query, produced on its own
    # thread one frame at a time (event_stream_codec.py).
    # ------------------------------------------------------------------

    def _transfer_frames(
        self, operation: str, metadata: bytes, source: Any
    ) -> AsyncIterator[bytes]:
        request = event_pb2.QueryRequest.FromString(metadata)
        return thread_frames(partial(self._produce_query, request))

    def _produce_query(
        self, request: event_pb2.QueryRequest, emit: Callable[[bytes], bool]
    ) -> None:
        with self._adapter.query_stored_stream(**_query_arguments(request)) as events:
            for frame in event_frames(events):
                if not emit(frame):
                    return

    @staticmethod
    def _transfer_error(exc: Exception) -> tuple[str, str] | None:
        if isinstance(exc, FilterError):
            return "INVALID_FILTER", str(exc)
        if isinstance(exc, EventNotFoundError):
            return "EVENT_NOT_FOUND", str(exc)
        code = authorization_error_code(exc)
        return (code, str(exc)) if code is not None else None

    async def _handle_max_seq(self, request: Request) -> None:
        await self._handle(
            request,
            event_pb2.MaxSeqRequest,
            event_pb2.MaxSeqResponse,
            self._call_max_seq,
        )

    def _call_max_seq(self, req: event_pb2.MaxSeqRequest) -> event_pb2.MaxSeqResponse:
        seq = self._adapter.max_seq(
            event_type=req.event_type if req.HasField("event_type") else None
        )
        return event_pb2.MaxSeqResponse(seq=seq)

    async def _handle_get_cursor(self, request: Request) -> None:
        await self._handle(
            request,
            event_pb2.GetCursorRequest,
            event_pb2.GetCursorResponse,
            self._call_get_cursor,
        )

    def _call_get_cursor(
        self, req: event_pb2.GetCursorRequest
    ) -> event_pb2.GetCursorResponse:
        last_seq = self._adapter.get_cursor(req.consumer_id, req.event_type)
        return event_pb2.GetCursorResponse(last_seq=last_seq)

    async def _handle_set_cursor(self, request: Request) -> None:
        await self._handle(
            request,
            event_pb2.SetCursorRequest,
            event_pb2.SetCursorResponse,
            self._call_set_cursor,
        )

    def _call_set_cursor(
        self, req: event_pb2.SetCursorRequest
    ) -> event_pb2.SetCursorResponse:
        self._adapter.set_cursor(req.consumer_id, req.event_type, req.last_seq)
        return event_pb2.SetCursorResponse()

    async def _handle_query_for_consumer(self, request: Request) -> None:
        await self._handle(
            request,
            event_pb2.QueryForConsumerRequest,
            event_pb2.QueryForConsumerResponse,
            self._call_query_for_consumer,
        )

    def _call_query_for_consumer(
        self, req: event_pb2.QueryForConsumerRequest
    ) -> event_pb2.QueryForConsumerResponse:
        rows = self._adapter.query_stored_for_consumer(
            consumer_id=req.consumer_id,
            event_type=req.event_type,
            limit=req.limit if req.HasField("limit") else None,
            filter=_struct_to_json_filter(req.HasField("json_filter"), req.json_filter),
        )
        return event_pb2.QueryForConsumerResponse(
            events=event_pb2.StoredEvents(events=[event_to_pb(row) for row in rows])
        )

    async def _handle_list_event_types(self, request: Request) -> None:
        await self._handle(
            request,
            event_pb2.ListEventTypesRequest,
            event_pb2.ListEventTypesResponse,
            self._call_list_event_types,
        )

    def _call_list_event_types(
        self, req: event_pb2.ListEventTypesRequest
    ) -> event_pb2.ListEventTypesResponse:
        summaries = self._adapter.event_types()
        return event_pb2.ListEventTypesResponse(
            types=event_pb2.EventTypeSummaries(
                types=[_type_to_pb(s) for s in summaries]
            )
        )
