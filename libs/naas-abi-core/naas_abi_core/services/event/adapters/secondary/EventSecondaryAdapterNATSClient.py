"""NATS RPC client adapter for the event kernel domain.

Implements ``IEventAdapter`` -- the durable-log secondary port -- by calling
out to a remote ``EventPrimaryAdapterNATS`` over NATS request/reply. See
``naas_abi_core/proto/event/v1/event.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there.

Scope note: this is a drop-in replacement for the ``adapter:`` argument of
``EventService(adapter, bus)``, nothing more. ``EventService.publish``,
``.query`` (the domain-level one, keyed by ``event_class: type``),
``.iter_query``, ``.iter_query_for_consumer``, ``.subscribe`` (bus-backed,
live, returns a ``Thread``), and ``.seek_consumer_to_end`` all keep running
100% locally against this client's six ``IEventAdapter`` methods -- none of
that is remoted here, and ``subscribe``'s bus broadcasting in particular is
entirely untouched by this adapter.

``nats-py`` has no synchronous client, so -- like
``naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter`` -- this
adapter bridges async NATS onto the synchronous port with ONE persistent
background thread running its own asyncio event loop (started lazily on
first use) and a single NATS connection reused across calls. Every
synchronous port method submits its async request via
``asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)`` and
blocks until it completes or raises, retrying once on a stale connection --
same shape as ``NATSJetStreamAdapter.publish``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``EventPrimaryAdapterNATS`` must read the token from
that exact header -- both sides read ``AUTH_HEADER`` from
``event_nats_contract``, a neutral module neither adapter owns, so this file
never has to import from the primary adapter's module (or vice versa) just
to agree on a header name.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import RLock, Thread
from typing import Self, TypeVar

import nats
from google.protobuf import struct_pb2
from google.protobuf.message import Message
from nats.aio.client import Client as NATSClient

from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import DEFAULT_TTL, issue_service_token
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.event.v1 import event_pb2
from naas_abi_core.services.event.adapters.event_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.event.EventPort import (
    EventNotFoundError,
    IEventAdapter,
    InvalidEventError,
    StoredEvent,
)

_DEFAULT_TIMEOUT_SECONDS = 10.0
# Reissue the token this long before it actually expires, so a call that's
# in flight while the token is borderline doesn't get rejected mid-request.
_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)

_ResponseT = TypeVar("_ResponseT", bound=Message)


def _pb_to_event(pb: event_pb2.StoredEvent) -> StoredEvent:
    return StoredEvent(
        id=pb.id,
        event_type=pb.event_type,
        seq=pb.seq,
        timestamp=pb.timestamp,
        payload=pb.payload,
    )


# mypy --follow-untyped-imports can't resolve google.protobuf's
# dynamically-generated Struct class through its stub package -- same known
# upstream quirk as the Timestamp one documented in pyproject.toml's
# `[[tool.mypy.overrides]] module = "naas_abi_core.proto.*"`, just triggered
# here because this hand-written code names the well-known type directly.
def _json_filter_to_struct(
    json_filter: dict | None,
) -> struct_pb2.Struct | None:  # type: ignore[name-defined]
    if json_filter is None:
        return None
    struct = struct_pb2.Struct()  # type: ignore[attr-defined]
    struct.update(json_filter)
    return struct


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``EventPrimaryAdapterNATS`` encodes
    errors. ``IEventAdapter`` itself declares no exceptions (they're raised
    by the domain ``EventService``, above this port) so ``EVENT_NOT_FOUND``/
    ``INVALID_EVENT`` are mapped defensively -- unlikely to actually
    round-trip from a real adapter -- and everything else, including
    ``INTERNAL``/``UNAUTHENTICATED``, surfaces as a ``RuntimeError``.
    """
    if error.code == "EVENT_NOT_FOUND":
        raise EventNotFoundError(error.message)
    if error.code == "INVALID_EVENT":
        raise InvalidEventError(error.message)
    raise RuntimeError(f"event NATS RPC failed ({error.code}): {error.message}")


class EventSecondaryAdapterNATSClient(IEventAdapter):
    """Calls a remote ``EventPrimaryAdapterNATS`` over NATS RPC."""

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
            name="event-nats-client-loop",
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
                    "EventSecondaryAdapterNATSClient: error closing stale connection"
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
                        f"event NATS RPC to {subject!r} failed"
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
    # IEventAdapter.
    # ------------------------------------------------------------------

    def append(
        self, event_id: str, event_type: str, timestamp: str, payload: bytes
    ) -> StoredEvent:
        request = event_pb2.AppendRequest(
            context=self._context(),
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.append", request, event_pb2.AppendResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_event(response.event)

    def query(
        self,
        event_type: str | None = None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        json_filter: dict | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        search: str | None = None,
    ) -> list[StoredEvent]:
        request = event_pb2.QueryRequest(
            context=self._context(),
            newest_first=newest_first,
        )
        if event_type is not None:
            request.event_type = event_type
        if since_seq is not None:
            request.since_seq = since_seq
        if until_seq is not None:
            request.until_seq = until_seq
        if since_timestamp is not None:
            request.since_timestamp = since_timestamp
        if until_timestamp is not None:
            request.until_timestamp = until_timestamp
        struct = _json_filter_to_struct(json_filter)
        if struct is not None:
            request.json_filter.CopyFrom(struct)
        if limit is not None:
            request.limit = limit
        if search is not None:
            request.search = search

        response = self._call(
            f"{SUBJECT_PREFIX}.query", request, event_pb2.QueryResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_event(pb) for pb in response.events.events]

    def max_seq(self, event_type: str | None = None) -> int:
        request = event_pb2.MaxSeqRequest(context=self._context())
        if event_type is not None:
            request.event_type = event_type
        response = self._call(
            f"{SUBJECT_PREFIX}.max_seq", request, event_pb2.MaxSeqResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.seq

    def get_cursor(self, consumer_id: str, event_type: str) -> int:
        request = event_pb2.GetCursorRequest(
            context=self._context(), consumer_id=consumer_id, event_type=event_type
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_cursor", request, event_pb2.GetCursorResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.last_seq

    def set_cursor(self, consumer_id: str, event_type: str, last_seq: int) -> None:
        request = event_pb2.SetCursorRequest(
            context=self._context(),
            consumer_id=consumer_id,
            event_type=event_type,
            last_seq=last_seq,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.set_cursor", request, event_pb2.SetCursorResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def query_for_consumer(
        self,
        consumer_id: str,
        event_type: str,
        limit: int | None = None,
        json_filter: dict | None = None,
    ) -> list[StoredEvent]:
        request = event_pb2.QueryForConsumerRequest(
            context=self._context(),
            consumer_id=consumer_id,
            event_type=event_type,
        )
        if limit is not None:
            request.limit = limit
        struct = _json_filter_to_struct(json_filter)
        if struct is not None:
            request.json_filter.CopyFrom(struct)

        response = self._call(
            f"{SUBJECT_PREFIX}.query_for_consumer",
            request,
            event_pb2.QueryForConsumerResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_event(pb) for pb in response.events.events]
