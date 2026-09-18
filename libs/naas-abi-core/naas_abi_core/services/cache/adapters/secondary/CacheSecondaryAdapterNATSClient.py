"""NATS RPC client adapter for the cache kernel domain.

Implements ``ICacheAdapter`` by calling out to a remote
``CachePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/cache/v1/cache.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there.

This is a *raw tier adapter*, exactly like ``CacheFSAdapter``/
``CacheRedisAdapter``/``ObjectStorageBackedAdapter``: it implements
``ICacheAdapter``'s five methods only, nothing about tiering or event
publishing. Plug it into a ``CacheAdapterEntry`` (one entry = one tier) the
same way any other cache adapter plugs in -- ``SingleTierCacheService``/
``CacheService`` wrap it exactly as they would a local adapter, and all
tiering + event-publishing behaviour keeps running unaffected on whichever
machine loads that tier's config, this client included.

``nats-py`` has no synchronous client, so -- like
``naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter`` and
``ObjectStorageSecondaryAdapterNATSClient`` -- this adapter bridges async
NATS onto the synchronous port with ONE persistent background thread running
its own asyncio event loop (started lazily on first use) and a single NATS
connection reused across calls. Every synchronous port method submits its
async request via
``asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)`` and
blocks until it completes or raises, retrying once on a stale connection --
same shape as ``NATSJetStreamAdapter.publish``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``CachePrimaryAdapterNATS`` must read the token from
that exact header -- both sides read ``AUTH_HEADER`` from
``cache_nats_contract``, a neutral module neither adapter owns, so this file
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
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import DEFAULT_TTL, issue_service_token
from naas_abi_core.proto.cache.v1 import cache_pb2
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.cache.adapters.cache_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheExpiredError,
    CacheNotFoundError,
    DataType,
    ICacheAdapter,
)
from nats.aio.client import Client as NATSClient

_DEFAULT_TIMEOUT_SECONDS = 10.0
# Reissue the token this long before it actually expires, so a call that's
# in flight while the token is borderline doesn't get rejected mid-request.
_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)

_ResponseT = TypeVar("_ResponseT", bound=Message)

_DATA_TYPE_TO_PB: dict[DataType, cache_pb2.DataType] = {
    DataType.TEXT: cache_pb2.DATA_TYPE_TEXT,
    DataType.JSON: cache_pb2.DATA_TYPE_JSON,
    DataType.BINARY: cache_pb2.DATA_TYPE_BINARY,
    DataType.PICKLE: cache_pb2.DATA_TYPE_PICKLE,
}
_PB_TO_DATA_TYPE: dict[int, DataType] = {
    pb_value: data_type for data_type, pb_value in _DATA_TYPE_TO_PB.items()
}


def _cached_data_to_pb(data: CachedData) -> cache_pb2.CachedData:
    return cache_pb2.CachedData(
        key=data.key,
        data=data.data,
        data_type=_DATA_TYPE_TO_PB[data.data_type],
        created_at=data.created_at,
    )


def _pb_to_cached_data(pb: cache_pb2.CachedData) -> CachedData:
    return CachedData(
        key=pb.key,
        data=pb.data,
        data_type=_PB_TO_DATA_TYPE[pb.data_type],
        created_at=pb.created_at,
    )


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``CachePrimaryAdapterNATS`` encodes
    errors -- the integration test asserts on the real exception types, not
    on the wire code.
    """
    if error.code == "CACHE_NOT_FOUND":
        raise CacheNotFoundError(error.message)
    if error.code == "CACHE_EXPIRED":
        raise CacheExpiredError(error.message)
    raise RuntimeError(f"cache NATS RPC failed ({error.code}): {error.message}")


class CacheSecondaryAdapterNATSClient(ICacheAdapter):
    """Calls a remote ``CachePrimaryAdapterNATS`` over NATS RPC."""

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
            name="cache-nats-client-loop",
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
                    "CacheSecondaryAdapterNATSClient: error closing stale connection"
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
                        f"cache NATS RPC to {subject!r} failed"
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
    # ICacheAdapter.
    # ------------------------------------------------------------------

    def get(self, key: str) -> CachedData:
        request = cache_pb2.GetRequest(context=self._context(), key=key)
        response = self._call(f"{SUBJECT_PREFIX}.get", request, cache_pb2.GetResponse)
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_cached_data(response.value)

    def set(self, key: str, value: CachedData) -> None:
        request = cache_pb2.SetRequest(
            context=self._context(), key=key, value=_cached_data_to_pb(value)
        )
        response = self._call(f"{SUBJECT_PREFIX}.set", request, cache_pb2.SetResponse)
        if response.HasField("error"):
            _raise_for_error(response.error)

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        request = cache_pb2.SetIfAbsentRequest(
            context=self._context(), key=key, value=_cached_data_to_pb(value)
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.set_if_absent",
            request,
            cache_pb2.SetIfAbsentResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.value

    def delete(self, key: str) -> None:
        request = cache_pb2.DeleteRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.delete", request, cache_pb2.DeleteResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def exists(self, key: str) -> bool:
        request = cache_pb2.ExistsRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.exists", request, cache_pb2.ExistsResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.value
