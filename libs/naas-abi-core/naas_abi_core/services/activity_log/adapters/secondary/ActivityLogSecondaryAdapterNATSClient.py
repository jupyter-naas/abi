"""NATS RPC client adapter for the activity_log kernel domain.

Implements ``IActivityLogAdapter`` by calling out to a remote
``ActivityLogPrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/activity_log/v1/activity_log.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
by the transport after failure; a timeout may hide a completed operation.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``ActivityLogPrimaryAdapterNATS`` must read the token
from that exact header -- both sides read ``AUTH_HEADER`` from
``activity_log_nats_contract``, a neutral module neither adapter owns, so
this file never has to import from the primary adapter's module (or vice
versa) just to agree on a header name.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.activity_log.v1 import activity_log_pb2
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
    pin_snapshot,
)
from naas_abi_core.services.activity_log.adapters.activity_log_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
    TRANSFER_PREFIX,
)
from naas_abi_core.services.activity_log.adapters.activity_log_stream_codec import (
    decode_events,
    event_to_pb,
    pb_to_event,
)


def _query_to_pb(query: ActivityLogQuery) -> activity_log_pb2.ActivityLogQueryFilter:
    pb = activity_log_pb2.ActivityLogQueryFilter()
    if query.event_type is not None:
        pb.event_type = query.event_type
    if query.since is not None:
        pb.since.FromDatetime(query.since)
    if query.until is not None:
        pb.until.FromDatetime(query.until)
    if query.limit is not None:
        pb.limit = query.limit
    pb.newest_first = query.newest_first
    if query.before_seq is not None:
        pb.before_seq = query.before_seq
    if query.after_seq is not None:
        pb.after_seq = query.after_seq
    return pb


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``ActivityLogPrimaryAdapterNATS``
    encodes errors. ``IActivityLogAdapter`` declares no domain-specific
    exceptions, so every error code -- including "INTERNAL" -- surfaces as a
    plain ``RuntimeError`` here; there is nothing more specific to raise.
    """
    raise RuntimeError(f"activity_log NATS RPC failed ({error.code}): {error.message}")


class ActivityLogSecondaryAdapterNATSClient(NatsRPCClient, IActivityLogAdapter):
    """Calls a remote ``ActivityLogPrimaryAdapterNATS`` over NATS RPC."""

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

    # ------------------------------------------------------------------
    # IActivityLogAdapter.
    # ------------------------------------------------------------------

    def record(self, event: ActivityEvent) -> None:
        request = activity_log_pb2.RecordRequest(
            context=self._context(), event=event_to_pb(event)
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.record", request, activity_log_pb2.RecordResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        request = activity_log_pb2.QueryRequest(
            context=self._context(),
            actor_id=actor_id,
            filter=_query_to_pb(query) if query is not None else None,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.query", request, activity_log_pb2.QueryResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [pb_to_event(pb) for pb in response.events.events]

    @contextmanager
    def query_stream(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> Iterator[Iterator[ActivityEvent]]:
        """Events fetched as the caller iterates, over a transfer stream
        (docs/adr/20261003_nats-streamed-results.md). The snapshot is pinned
        here, before the stream opens, so an event recorded after the block
        opened is never included. Leaving the block closes the session."""
        pinned = pin_snapshot(self.query, actor_id, query)
        if pinned is None:
            yield iter(())
            return
        request = activity_log_pb2.QueryRequest(
            actor_id=actor_id, filter=_query_to_pb(pinned)
        )
        with self._transfer_stream(
            TRANSFER_PREFIX, "query", request.SerializeToString(), _raise_for_error
        ) as frames:
            if frames is None:
                raise RuntimeError(
                    "activity_log NATS RPC failed (UNAVAILABLE): "
                    "no engine streams activity logs"
                )
            yield (event for frame in frames for event in decode_events(frame))

    def list_actors(self) -> list[str]:
        request = activity_log_pb2.ListActorsRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.list_actors",
            request,
            activity_log_pb2.ListActorsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return list(response.actors.actors)

    def shutdown(self) -> None:
        request = activity_log_pb2.ShutdownRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.shutdown", request, activity_log_pb2.ShutdownResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
