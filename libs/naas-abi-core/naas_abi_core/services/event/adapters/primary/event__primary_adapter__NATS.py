"""NATS RPC primary adapter for the event kernel domain.

Exposes a real ``IEventAdapter`` as a NATS micro-service (see
``naas_abi_core/proto/event/v1/event.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there). This is the
server side; the matching client is ``EventSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``event_nats_contract`` below -- that's a
neutral module neither adapter owns, so this file and the client's don't
depend on each other; see that module's docstring for why).

Scope note: this wraps a raw ``IEventAdapter`` -- the durable-log secondary
port -- not the domain ``EventService``. There is no richer domain behaviour
to preserve at this port boundary: ``EventService``'s extra behaviour (bus
broadcasting on ``publish``, live ``subscribe``, generator-based
``iter_query``/``iter_query_for_consumer``, class<->IRI resolution) is
layered *above* this port, in ``EventService`` itself, wherever it is
constructed -- not something this adapter needs to replicate. Consequently
this primary adapter has no bus access and registers endpoints only for
``IEventAdapter``'s six methods.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import nats
import nats.micro
from google.protobuf import struct_pb2
from google.protobuf.message import DecodeError, Message
from nats.micro.request import Request
from nats.micro.service import Service

from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import respond_protobuf
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.event.v1 import event_pb2
from naas_abi_core.services.event.adapters.event_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.event.EventPort import (
    EventNotFoundError,
    IEventAdapter,
    InvalidEventError,
    StoredEvent,
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


def _event_to_pb(event: StoredEvent) -> event_pb2.StoredEvent:
    return event_pb2.StoredEvent(
        id=event.id,
        event_type=event.event_type,
        seq=event.seq,
        timestamp=event.timestamp,
        payload=event.payload,
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


class EventPrimaryAdapterNATS:
    """Serves the event durable-log port over NATS RPC (request/reply).

    Wraps a real ``IEventAdapter`` and registers one NATS micro-service
    endpoint per port method. Each endpoint authenticates the caller via
    ``Nats-Auth-Token`` before doing anything else, then decodes the
    Protobuf request, calls straight through to the wrapped adapter, and
    encodes a Protobuf response. Errors -- auth failures, unexpected
    exceptions -- are always reported as a normal response carrying a
    populated ``CallError``, never as a crashed handler or a raw NATS-level
    error.

    Accepts a bare ``IEventAdapter`` -- there is no richer domain object to
    prefer here (unlike ``object_storage``'s primary adapter, which prefers
    the domain service to preserve its event-publishing side effects):
    ``EventService``'s extra behaviour lives above this port entirely, so
    wrapping the adapter is the only correct choice, not a shortcut.
    """

    def __init__(self, adapter: IEventAdapter, jwt_secret: str) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``event`` NATS service on ``nc``.

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
        self._service = service

    async def stop(self) -> None:
        """Deregister the service, draining its subscriptions."""
        service = self._service
        self._service = None
        try:
            if service is not None:
                await service.stop()
        finally:
            self._dispatch.close()

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
            response = await self._dispatch.call(call, parsed_request)
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
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"EventPrimaryAdapterNATS: unexpected error handling {request.subject!r}"
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
    # Endpoint handlers -- one per IEventAdapter method.
    # ------------------------------------------------------------------

    async def _handle_append(self, request: Request) -> None:
        await self._handle(
            request,
            event_pb2.AppendRequest,
            event_pb2.AppendResponse,
            self._call_append,
        )

    def _call_append(self, req: event_pb2.AppendRequest) -> event_pb2.AppendResponse:
        stored = self._adapter.append(
            event_id=req.event_id,
            event_type=req.event_type,
            timestamp=req.timestamp,
            payload=req.payload,
        )
        return event_pb2.AppendResponse(event=_event_to_pb(stored))

    async def _handle_query(self, request: Request) -> None:
        await self._handle(
            request,
            event_pb2.QueryRequest,
            event_pb2.QueryResponse,
            self._call_query,
        )

    def _call_query(self, req: event_pb2.QueryRequest) -> event_pb2.QueryResponse:
        rows = self._adapter.query(
            event_type=req.event_type if req.HasField("event_type") else None,
            since_seq=req.since_seq if req.HasField("since_seq") else None,
            until_seq=req.until_seq if req.HasField("until_seq") else None,
            since_timestamp=req.since_timestamp
            if req.HasField("since_timestamp")
            else None,
            until_timestamp=req.until_timestamp
            if req.HasField("until_timestamp")
            else None,
            json_filter=_struct_to_json_filter(
                req.HasField("json_filter"), req.json_filter
            ),
            limit=req.limit if req.HasField("limit") else None,
            newest_first=req.newest_first,
            search=req.search if req.HasField("search") else None,
        )
        return event_pb2.QueryResponse(
            events=event_pb2.StoredEvents(events=[_event_to_pb(row) for row in rows])
        )

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
        rows = self._adapter.query_for_consumer(
            consumer_id=req.consumer_id,
            event_type=req.event_type,
            limit=req.limit if req.HasField("limit") else None,
            json_filter=_struct_to_json_filter(
                req.HasField("json_filter"), req.json_filter
            ),
        )
        return event_pb2.QueryForConsumerResponse(
            events=event_pb2.StoredEvents(events=[_event_to_pb(row) for row in rows])
        )
