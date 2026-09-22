"""NATS RPC primary adapter for the activity_log kernel domain.

Exposes a real ``IActivityLogAdapter`` as a NATS micro-service (see
``naas_abi_core/proto/activity_log/v1/activity_log.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there). This
is the server side; the matching client is
``ActivityLogSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``activity_log_nats_contract`` below --
that's a neutral module neither adapter owns, so this file and the client's
don't depend on each other; see that module's docstring for why).

``shutdown`` is exposed as a plain RPC endpoint too, for a complete 1:1
mirror of ``IActivityLogAdapter`` -- even though remoting a "shut down my
local resources" call is a little unusual for an RPC target: there is no
meaningful cross-process action a remote caller should trigger on demand
this way, and a NATS-connected client tearing down the *server's* wrapped
adapter out from under every other caller would be surprising. The handler
still forwards the call through rather than silently dropping it, matching
every other endpoint's "always call straight through" behaviour.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC
from typing import TypeVar

import nats
import nats.micro
from google.protobuf import json_format
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.proto.activity_log.v1 import activity_log_pb2
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
    IActivityLogDomain,
)
from naas_abi_core.services.activity_log.adapters.activity_log_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "ActivityLogPrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


def _event_to_pb(event: ActivityEvent) -> activity_log_pb2.ActivityEvent:
    pb = activity_log_pb2.ActivityEvent(
        actor_id=event.actor_id,
        event_type=event.event_type,
    )
    pb.timestamp.FromDatetime(event.timestamp)
    if event.correlation_id is not None:
        pb.correlation_id = event.correlation_id
    pb.attributes.update(event.attributes)
    return pb


def _pb_to_event(pb: activity_log_pb2.ActivityEvent) -> ActivityEvent:
    return ActivityEvent(
        actor_id=pb.actor_id,
        event_type=pb.event_type,
        timestamp=pb.timestamp.ToDatetime(tzinfo=UTC),
        correlation_id=pb.correlation_id if pb.HasField("correlation_id") else None,
        attributes=json_format.MessageToDict(pb.attributes),
    )


def _pb_to_query(pb: activity_log_pb2.ActivityLogQueryFilter) -> ActivityLogQuery:
    return ActivityLogQuery(
        event_type=pb.event_type if pb.HasField("event_type") else None,
        since=pb.since.ToDatetime(tzinfo=UTC) if pb.HasField("since") else None,
        until=pb.until.ToDatetime(tzinfo=UTC) if pb.HasField("until") else None,
        limit=pb.limit if pb.HasField("limit") else None,
    )


class ActivityLogPrimaryAdapterNATS:
    """Serves activity_log over NATS RPC (request/reply).

    Wraps a real adapter *or* the domain service and registers one NATS
    micro-service endpoint per ``IActivityLogAdapter`` method. Each endpoint
    authenticates the caller via ``Nats-Auth-Token`` before doing anything
    else, then decodes the Protobuf request, calls straight through to the
    wrapped object, and encodes a Protobuf response. Errors -- auth
    failures, anything unexpected -- are always reported as a normal
    response carrying a populated ``CallError``, never as a crashed handler
    or a raw NATS-level error.

    Accepts either an ``IActivityLogAdapter`` (a bare secondary adapter,
    e.g. in tests) or an ``ActivityLogService``/``IActivityLogDomain`` (the
    real engine-loaded domain service) -- deliberately, not for convenience:
    wrapping the raw adapter instead of the domain service would silently
    skip ``ActivityLogService``'s fail-open behaviour (swallowing adapter
    exceptions from ``record()`` and just logging a warning) for every
    remote caller, which would only diverge from in-process behaviour, not
    match it -- a remote ``record()`` call should never break the caller's
    request any more than a local one does. ``EngineNATSLoader`` always
    passes the domain service.
    """

    def __init__(
        self,
        adapter: IActivityLogAdapter | IActivityLogDomain,
        jwt_secret: str,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``activity_log`` NATS service on ``nc``.

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
            description="ABI kernel activity_log domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="record",
            subject=f"{SUBJECT_PREFIX}.record",
            handler=self._handle_record,
        )
        await service.add_endpoint(
            name="query",
            subject=f"{SUBJECT_PREFIX}.query",
            handler=self._handle_query,
        )
        await service.add_endpoint(
            name="list_actors",
            subject=f"{SUBJECT_PREFIX}.list_actors",
            handler=self._handle_list_actors,
        )
        await service.add_endpoint(
            name="shutdown",
            subject=f"{SUBJECT_PREFIX}.shutdown",
            handler=self._handle_shutdown,
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
        parsed_request.ParseFromString(request.data)

        try:
            # The adapter port is synchronous and may block for seconds (network
            # round trips, slow backends). Every primary shares ONE event loop and
            # ONE connection (nats_runtime), so run the call on a worker thread:
            # inline it would stall every other endpoint of every service in the
            # process, plus nats-py's own PING/PONG handling.
            response = await asyncio.to_thread(call, parsed_request)
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"ActivityLogPrimaryAdapterNATS: unexpected error handling {request.subject!r}"
            )
            await self._respond_error(
                request, response_cls, "INTERNAL", "internal error", retryable=True
            )
            return

        await request.respond(response.SerializeToString())

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
        await request.respond(response.SerializeToString())

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per IActivityLogAdapter method.
    # ------------------------------------------------------------------

    async def _handle_record(self, request: Request) -> None:
        await self._handle(
            request,
            activity_log_pb2.RecordRequest,
            activity_log_pb2.RecordResponse,
            self._call_record,
        )

    def _call_record(
        self, req: activity_log_pb2.RecordRequest
    ) -> activity_log_pb2.RecordResponse:
        self._adapter.record(_pb_to_event(req.event))
        return activity_log_pb2.RecordResponse()

    async def _handle_query(self, request: Request) -> None:
        await self._handle(
            request,
            activity_log_pb2.QueryRequest,
            activity_log_pb2.QueryResponse,
            self._call_query,
        )

    def _call_query(
        self, req: activity_log_pb2.QueryRequest
    ) -> activity_log_pb2.QueryResponse:
        query = _pb_to_query(req.filter) if req.HasField("filter") else None
        events = self._adapter.query(req.actor_id, query)
        return activity_log_pb2.QueryResponse(
            events=activity_log_pb2.ActivityEvents(
                events=[_event_to_pb(event) for event in events]
            )
        )

    async def _handle_list_actors(self, request: Request) -> None:
        await self._handle(
            request,
            activity_log_pb2.ListActorsRequest,
            activity_log_pb2.ListActorsResponse,
            self._call_list_actors,
        )

    def _call_list_actors(
        self, req: activity_log_pb2.ListActorsRequest
    ) -> activity_log_pb2.ListActorsResponse:
        actors = self._adapter.list_actors()
        return activity_log_pb2.ListActorsResponse(
            actors=activity_log_pb2.Actors(actors=actors)
        )

    async def _handle_shutdown(self, request: Request) -> None:
        await self._handle(
            request,
            activity_log_pb2.ShutdownRequest,
            activity_log_pb2.ShutdownResponse,
            self._call_shutdown,
        )

    def _call_shutdown(
        self, req: activity_log_pb2.ShutdownRequest
    ) -> activity_log_pb2.ShutdownResponse:
        self._adapter.shutdown()
        return activity_log_pb2.ShutdownResponse()
