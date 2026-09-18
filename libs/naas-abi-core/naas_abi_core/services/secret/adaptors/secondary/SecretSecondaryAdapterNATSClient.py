"""NATS RPC client adapter for the secret kernel domain.

Implements ``ISecretAdapter`` by calling out to a remote
``SecretPrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/secret/v1/secret.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there.

Security note: Stage 1's shared-JWT auth has no per-caller authorization --
see ``secret_nats_contract.py``'s docstring. Ported anyway, an explicit,
accepted, temporary gap.

``nats-py`` has no synchronous client, so -- like every other
``*SecondaryAdapterNATSClient`` in this codebase -- this adapter bridges
async NATS onto the synchronous port with ONE persistent background thread
running its own asyncio event loop (started lazily on first use) and a
single NATS connection reused across calls. Every synchronous port method
submits its async request via
``asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)`` and
blocks until it completes or raises, retrying once on a stale connection.

Plugs into ``Secret``'s existing multi-adapter fan-out exactly like
``dotenv``/``naas``/``base64`` already do: add ``{adapter: "nats_rpc",
config: {...}}`` as one more entry in ``services.secret.secret_adapters``.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import RLock, Thread
from typing import Any, Self, TypeVar

import nats
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import DEFAULT_TTL, issue_service_token
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.secret.v1 import secret_pb2
from naas_abi_core.services.secret.adaptors.secret_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.secret.SecretPorts import (
    ISecretAdapter,
    SecretAuthenticationError,
)
from nats.aio.client import Client as NATSClient

_DEFAULT_TIMEOUT_SECONDS = 10.0
# Reissue the token this long before it actually expires, so a call that's
# in flight while the token is borderline doesn't get rejected mid-request.
_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)

_ResponseT = TypeVar("_ResponseT", bound=Message)


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``SecretPrimaryAdapterNATS``
    encodes errors.
    """
    if error.code == "SECRET_AUTH_FAILED":
        raise SecretAuthenticationError(error.message)
    raise RuntimeError(f"secret NATS RPC failed ({error.code}): {error.message}")


class SecretSecondaryAdapterNATSClient(ISecretAdapter):
    """Calls a remote ``SecretPrimaryAdapterNATS`` over NATS RPC."""

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
        # loop, mirroring every other *SecondaryAdapterNATSClient here.
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
    # Persistent background event loop, same shape as every sibling client.
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
            name="secret-nats-client-loop",
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
                # Best-effort close of a connection we're discarding anyway.
                logger.opt(exception=True).debug(
                    "SecretSecondaryAdapterNATSClient: error closing stale connection"
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
                        f"secret NATS RPC to {subject!r} failed"
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
    # ISecretAdapter.
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> str | Any | None:
        request = secret_pb2.GetRequest(context=self._context(), key=key)
        response = self._call(f"{SUBJECT_PREFIX}.get", request, secret_pb2.GetResponse)
        if response.HasField("error"):
            _raise_for_error(response.error)
        if response.found.HasField("value"):
            return response.found.value
        return default

    def set(self, key: str, value: str) -> None:
        request = secret_pb2.SetRequest(context=self._context(), key=key, value=value)
        response = self._call(f"{SUBJECT_PREFIX}.set", request, secret_pb2.SetResponse)
        if response.HasField("error"):
            _raise_for_error(response.error)

    def remove(self, key: str) -> None:
        request = secret_pb2.RemoveRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.remove", request, secret_pb2.RemoveResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def list(self) -> dict[str, str | None]:
        request = secret_pb2.ListRequest(context=self._context())
        response = self._call(f"{SUBJECT_PREFIX}.list", request, secret_pb2.ListResponse)
        if response.HasField("error"):
            _raise_for_error(response.error)
        return {
            entry.key: (entry.value if entry.HasField("value") else None)
            for entry in response.found.entries
        }
