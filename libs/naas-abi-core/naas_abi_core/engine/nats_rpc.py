"""Shared transport for synchronous protobuf RPC adapters over Core NATS.

A call is attempted once. Transport failure does not prove that a remote side
effect did not happen; callers must reconcile uncertain outcomes before retrying.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import RLock, Thread
from typing import Any, Self, TypeVar, cast

from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import DEFAULT_TTL, issue_service_token
from naas_abi_core.proto.common.v1 import common_pb2
from nats.aio.client import Client as NATSClient
from nats.errors import MaxPayloadError
from nats.micro.request import ERROR_CODE_HEADER, ERROR_HEADER, Request

MAX_RPC_PAYLOAD = 8 * 1024 * 1024
_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)
_ResponseT = TypeVar("_ResponseT", bound=Message)


class NatsRPCError(RuntimeError):
    """A transport-level RPC error, independent of a domain's error mapping."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"NATS RPC failed ({code}): {message}")


class NatsRPCPayloadTooLargeError(NatsRPCError):
    """Use streaming or a storage reference instead of replaying this call."""

    def __init__(self, message: str) -> None:
        super().__init__("PAYLOAD_TOO_LARGE", message)


def _call_error(response: Message) -> common_pb2.CallError:
    # Some contracts wrap CallError with typed domain details (DatasetError).
    error = cast(Any, response).error
    while not isinstance(error, common_pb2.CallError):
        error = error.error
    return error


async def respond_protobuf(
    request: Request, response: Message, response_cls: Callable[..., Message]
) -> None:
    """Replace an oversized reply with a small, non-retryable protobuf error."""
    payload = response.SerializeToString()
    try:
        if len(payload) > MAX_RPC_PAYLOAD:
            raise MaxPayloadError()
        await request.respond(payload)
    except MaxPayloadError:
        error_response = response_cls()
        _call_error(error_response).CopyFrom(
            common_pb2.CallError(
                code="PAYLOAD_TOO_LARGE",
                message="Reply exceeds the payload limit; use streaming or a storage reference. "
                "The operation may already have completed; do not replay it automatically.",
                retryable=False,
            )
        )
        await request.respond(error_response.SerializeToString())


class NatsRPCClient:
    """Owns one lazy connection and loop; domain subclasses own wire mappings."""

    def __init__(
        self,
        nats_url: str,
        jwt_secret: str,
        service_identity: str,
        timeout_seconds: float = 10.0,
        *,
        auth_header: str = "Nats-Auth-Token",
    ) -> None:
        self._auth_header = auth_header
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
            loop.call_soon(ready.set)
            try:
                loop.run_forever()
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

        thread = Thread(
            target=_run,
            daemon=True,
            name="nats-rpc-client-loop",
        )
        thread.start()
        ready.wait()
        self._loop = holder["loop"]
        self._loop_thread = thread
        return self._loop

    def _run_coro(self, coro, timeout: float | None = None):
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(
                timeout=timeout if timeout is not None else self._timeout_seconds + 1.0
            )
        except FutureTimeoutError:
            # Cancel local waiting, not remote work that may already have committed.
            future.cancel()
            raise

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
        if self._nc is not None and not self._nc.is_closed:
            return self._nc
        nc = NATSClient()
        self._nc = nc
        try:
            # Do not queue an RPC during reconnect to execute after its deadline.
            await nc.connect(self._nats_url, pending_size=0)
        except BaseException:
            await nc.close()
            self._nc = None
            raise
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
                    "NatsRPCClient: error closing stale connection"
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
            headers = {self._auth_header: self._current_token()}
            msg = self._run_coro(
                asyncio.wait_for(
                    self._do_request_async(subject, payload, headers),
                    timeout=self._timeout_seconds,
                )
            )

        reply_headers = msg.headers or {}
        if ERROR_HEADER in reply_headers or ERROR_CODE_HEADER in reply_headers:
            raise NatsRPCError(
                reply_headers.get(ERROR_CODE_HEADER, "UNKNOWN"),
                reply_headers.get(ERROR_HEADER, "remote service error"),
            )

        response = response_cls()
        response.ParseFromString(msg.data)
        if response.HasField("error"):
            error = _call_error(response)
            if error.code == "PAYLOAD_TOO_LARGE":
                raise NatsRPCPayloadTooLargeError(error.message)
        return response

    async def _do_request_async(
        self, subject: str, payload: bytes, headers: dict[str, str]
    ):
        nc = await self._ensure_connection_async()
        # NATS counts the HPUB header block as part of the message size. nats-py's
        # publish check only counts the body, so check both before sending.
        header_size = len(b"NATS/1.0\r\n\r\n") + sum(
            len(f"{key}: {value}\r\n".encode()) for key, value in headers.items()
        )
        limit = min(nc.max_payload, MAX_RPC_PAYLOAD)
        if len(payload) + header_size > limit:
            raise NatsRPCPayloadTooLargeError(
                f"Request exceeds {limit} bytes including headers; "
                "use streaming or a storage reference."
            )
        try:
            return await nc.request(
                subject, payload, timeout=self._timeout_seconds, headers=headers
            )
        except MaxPayloadError as exc:
            raise NatsRPCPayloadTooLargeError(
                "Request exceeds the server payload limit; use streaming or a storage reference."
            ) from exc
