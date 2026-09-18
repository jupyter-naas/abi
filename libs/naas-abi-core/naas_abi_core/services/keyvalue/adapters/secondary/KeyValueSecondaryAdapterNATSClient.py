"""NATS RPC client adapter for the keyvalue kernel domain.

Implements ``IKeyValueAdapter`` by calling out to a remote
``KeyValuePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/keyvalue/v1/keyvalue.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there.

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
than on every call. ``KeyValuePrimaryAdapterNATS`` must read the token from
that exact header -- both sides read ``AUTH_HEADER`` from
``keyvalue_nats_contract``, a neutral module neither adapter owns, so this
file never has to import from the primary adapter's module (or vice versa)
just to agree on a header name.

``KeyValueService.lock()`` is explicitly out of scope for this v1 contract
(see the ``.proto`` file's header comment): it isn't part of
``IKeyValueAdapter``, so there is no NATS subject for it either -- it keeps
working transparently against this adapter, composed purely from ``set``
``set_if_not_exists``/``delete_if_value_matches`` below plus a client-side
retry/backoff loop, each call simply going over the wire.
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
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.keyvalue.v1 import keyvalue_pb2
from naas_abi_core.services.keyvalue.adapters.keyvalue_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import (
    IKeyValueAdapter,
    KVLockTimeoutError,
    KVNotFoundError,
)
from nats.aio.client import Client as NATSClient

_DEFAULT_TIMEOUT_SECONDS = 10.0
# Reissue the token this long before it actually expires, so a call that's
# in flight while the token is borderline doesn't get rejected mid-request.
_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)

_ResponseT = TypeVar("_ResponseT", bound=Message)


def _raise_for_error(
    error: common_pb2.CallError,
    lock_timeout_detail: keyvalue_pb2.KVLockTimeoutDetail | None = None,
) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``KeyValuePrimaryAdapterNATS``
    encodes errors -- the generic adapter contract test asserts on the real
    exception types, not on the wire code.
    """
    if error.code == "KV_NOT_FOUND":
        raise KVNotFoundError(error.message)
    if error.code == "KV_LOCK_TIMEOUT":
        if lock_timeout_detail is not None:
            raise KVLockTimeoutError(
                key=lock_timeout_detail.key,
                attempts=lock_timeout_detail.attempts,
                timeout=lock_timeout_detail.timeout_seconds,
            )
        raise RuntimeError(f"keyvalue NATS RPC failed ({error.code}): {error.message}")
    raise RuntimeError(f"keyvalue NATS RPC failed ({error.code}): {error.message}")


class KeyValueSecondaryAdapterNATSClient(IKeyValueAdapter):
    """Calls a remote ``KeyValuePrimaryAdapterNATS`` over NATS RPC."""

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
            name="keyvalue-nats-client-loop",
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
                    "KeyValueSecondaryAdapterNATSClient: error closing stale connection"
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
                        f"keyvalue NATS RPC to {subject!r} failed"
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
    # IKeyValueAdapter.
    # ------------------------------------------------------------------

    def get(self, key: str) -> bytes:
        request = keyvalue_pb2.GetRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.get", request, keyvalue_pb2.GetResponse
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )
        return response.value

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        request = keyvalue_pb2.SetRequest(
            context=self._context(), key=key, value=value, ttl=ttl
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.set", request, keyvalue_pb2.SetResponse
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )

    def set_if_not_exists(
        self,
        key: str,
        value: bytes,
        ttl: int | None = None,
    ) -> bool:
        request = keyvalue_pb2.SetIfNotExistsRequest(
            context=self._context(), key=key, value=value, ttl=ttl
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.set_if_not_exists",
            request,
            keyvalue_pb2.SetIfNotExistsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )
        return response.ok_value

    def delete(self, key: str) -> None:
        request = keyvalue_pb2.DeleteRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.delete", request, keyvalue_pb2.DeleteResponse
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        request = keyvalue_pb2.DeleteIfValueMatchesRequest(
            context=self._context(), key=key, value=value
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.delete_if_value_matches",
            request,
            keyvalue_pb2.DeleteIfValueMatchesResponse,
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )
        return response.ok_value

    def exists(self, key: str) -> bool:
        request = keyvalue_pb2.ExistsRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.exists", request, keyvalue_pb2.ExistsResponse
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )
        return response.ok_value
