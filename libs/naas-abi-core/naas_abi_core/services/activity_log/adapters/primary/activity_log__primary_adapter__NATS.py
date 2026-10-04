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

from collections.abc import AsyncIterator, Callable
from datetime import UTC
from functools import partial
from typing import Any, TypeVar

import nats
import nats.micro
from google.protobuf.message import DecodeError, Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import (
    RequestPayloadError,
    request_payload,
    respond_protobuf,
)
from naas_abi_core.engine.nats_tracing import TracedService, add_traced_service
from naas_abi_core.engine.nats_transfer import TransferHost, thread_frames
from naas_abi_core.proto.activity_log.v1 import activity_log_pb2
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityLogQuery,
    IActivityLogAdapter,
    IActivityLogDomain,
)
from naas_abi_core.services.activity_log.adapters.activity_log_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
    TRANSFER_PREFIX,
)
from naas_abi_core.services.activity_log.adapters.activity_log_stream_codec import (
    activity_frames,
    event_to_pb,
    pb_to_event,
)
from nats.micro.request import Request

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "ActivityLogPrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


def _pb_to_query(pb: activity_log_pb2.ActivityLogQueryFilter) -> ActivityLogQuery:
    return ActivityLogQuery(
        event_type=pb.event_type if pb.HasField("event_type") else None,
        since=pb.since.ToDatetime(tzinfo=UTC) if pb.HasField("since") else None,
        until=pb.until.ToDatetime(tzinfo=UTC) if pb.HasField("until") else None,
        limit=pb.limit if pb.HasField("limit") else None,
        newest_first=pb.newest_first,
        before_seq=pb.before_seq if pb.HasField("before_seq") else None,
        after_seq=pb.after_seq if pb.HasField("after_seq") else None,
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
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._service: TracedService | None = None
        # Streamed queries (docs/adr/20261003_nats-streamed-results.md).
        self._transfer = TransferHost(
            TRANSFER_PREFIX,
            jwt_secret,
            self._transfer_frames,
            operations=("query",),
            chunk_bytes=1024 * 1024,
        )

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``activity_log`` NATS service on ``nc``.

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
        await self._transfer.start(nc)

    async def stop(self) -> None:
        """Deregister the service, draining its subscriptions."""
        await self._transfer.stop()
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
            response = await self._dispatch.call(call, parsed_request)
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"ActivityLogPrimaryAdapterNATS: unexpected error handling {request.subject!r}"
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
        self._adapter.record(pb_to_event(req.event))
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
                events=[event_to_pb(event) for event in events]
            )
        )

    # ------------------------------------------------------------------
    # Streamed queries: one transfer session per query, produced on its own
    # thread one frame at a time (activity_log_stream_codec.py).
    # ------------------------------------------------------------------

    def _transfer_frames(
        self, operation: str, metadata: bytes, source: Any
    ) -> AsyncIterator[bytes]:
        request = activity_log_pb2.QueryRequest.FromString(metadata)
        return thread_frames(partial(self._produce_query, request))

    def _produce_query(
        self, request: activity_log_pb2.QueryRequest, emit: Callable[[bytes], bool]
    ) -> None:
        query = _pb_to_query(request.filter) if request.HasField("filter") else None
        with self._adapter.query_stream(request.actor_id, query) as events:
            for frame in activity_frames(events):
                if not emit(frame):
                    return

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
