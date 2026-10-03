"""Shared transport for synchronous protobuf RPC adapters over Core NATS.

A call is attempted once. Transport failure does not prove that a remote side
effect did not happen; callers must reconcile uncertain outcomes before retrying.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import RLock, Thread
from typing import Any, Self, TypeVar, cast

from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine import nats_overflow
from naas_abi_core.engine.nats_auth import (
    DEFAULT_TTL,
    InvalidServiceTokenError,
    issue_service_token,
)
from naas_abi_core.engine.nats_naming import connection_name, rpc_client_role
from naas_abi_core.engine.nats_transfer import TransferError
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_proto.transfer.v1 import transfer_pb2 as transfer_pb
from naas_abi_sdk import overflow
from naas_abi_sdk.telemetry import (
    TransferTrace,
    client_span,
    record_error,
    record_overflow,
    record_reply,
    transfer_span,
)
from naas_abi_sdk.transfer import transfer_subject
from nats.aio.client import Client as NATSClient
from nats.errors import MaxPayloadError, NoRespondersError
from nats.micro.request import ERROR_CODE_HEADER, ERROR_HEADER, Request

_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)
_ResponseT = TypeVar("_ResponseT", bound=Message)


# Reply header naming the CallError code of an error reply (ABI-level, not micro).
ERROR_CODE_REPLY_HEADER = "Abi-Error-Code"


class NatsRPCError(RuntimeError):
    """A transport-level RPC error, independent of a domain's error mapping."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"NATS RPC failed ({code}): {message}")


class NatsRPCPayloadTooLargeError(NatsRPCError):
    """Use streaming or a storage reference instead of replaying this call.

    ``unsent``: refused before anything left this process (the client's own
    size check), so the call can still go through the overflow upload.
    """

    def __init__(self, message: str, *, unsent: bool = False) -> None:
        self.unsent = unsent
        super().__init__("PAYLOAD_TOO_LARGE", message)


class RequestPayloadError(Exception):
    """An overflowed request body the primary could not read; reply with it."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


async def request_payload(request: Request) -> bytes:
    """The request's protobuf body, read from its overflow upload when it has one.

    Primaries call this instead of reading ``request.data`` (see
    docs/adr/20261003_nats-rpc-overflow.md).
    """
    headers = request.headers or {}
    transfer_id = headers.get(overflow.REQUEST_HEADER)
    if not transfer_id:
        return request.data
    host = nats_overflow.current()
    if host is None:
        raise RequestPayloadError(
            "UNAVAILABLE", "This process cannot read overflowed requests"
        )
    try:
        return await host.fetch(transfer_id, headers)
    except TransferError as exc:
        raise RequestPayloadError(exc.code, str(exc)) from exc
    except TimeoutError as exc:
        raise RequestPayloadError(
            "DEADLINE_EXCEEDED", "Reading the overflowed request timed out"
        ) from exc


def _call_error(response: Message) -> common_pb2.CallError:
    # Some contracts wrap CallError with typed domain details (DatasetError).
    error = cast(Any, response).error
    while not isinstance(error, common_pb2.CallError):
        error = error.error
    return error


def _error_code(response: Message) -> str:
    try:
        if not response.HasField("error"):
            return ""
    except ValueError:  # a response type without an error field
        return ""
    return _call_error(response).code


async def respond_protobuf(
    request: Request, response: Message, response_cls: Callable[..., Message]
) -> None:
    """Reply; replace an oversized reply with a small, non-retryable protobuf error.

    Error replies also carry their code in the ``Abi-Error-Code`` header (for the
    traffic view, which never reads payloads) and fail the current trace span.
    """
    payload = response.SerializeToString()
    code = _error_code(response)
    if code:
        record_error(code, _call_error(response).message)
    headers = {ERROR_CODE_REPLY_HEADER: code} if code else None
    try:
        # The broker's max_payload is the only limit. It counts the header
        # block, which nats-py's own check does not; a violation closes the
        # connection every primary in this process shares.
        limit = _broker_limit(request)
        if limit is not None and message_size(payload, headers) > limit:
            raise MaxPayloadError()
        await request.respond(payload, headers=headers)
    except MaxPayloadError:
        if await _respond_overflow(request, payload):
            return
        error_response = response_cls()
        _call_error(error_response).CopyFrom(
            common_pb2.CallError(
                code="PAYLOAD_TOO_LARGE",
                message="Reply exceeds the payload limit; use streaming or a storage reference. "
                "The operation may already have completed; do not replay it automatically.",
                retryable=False,
            )
        )
        record_error("PAYLOAD_TOO_LARGE")
        await request.respond(
            error_response.SerializeToString(),
            headers={ERROR_CODE_REPLY_HEADER: "PAYLOAD_TOO_LARGE"},
        )


def message_size(payload: bytes, headers: dict[str, str] | None) -> int:
    """Bytes NATS counts against max_payload: the body and the header block."""
    if not headers:
        return len(payload)
    block = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    return len(payload) + len(f"NATS/1.0\r\n{block}\r\n".encode())


def _broker_limit(request: Request) -> int | None:
    """The max_payload of the connection a request arrived on."""
    client = getattr(getattr(request, "_msg", None), "_client", None)
    limit = getattr(client, "max_payload", None)
    return limit if isinstance(limit, int) and limit > 0 else None


async def _respond_overflow(request: Request, payload: bytes) -> bool:
    """Park a reply that does not fit, for a client that can read it."""
    headers = request.headers or {}
    host = nats_overflow.current()
    if (
        host is None
        or headers.get(overflow.ACCEPT_HEADER) != "1"
        or not host.accepts(len(payload))
    ):
        return False
    try:
        transfer_id = await host.park(headers, payload)
    except (TransferError, InvalidServiceTokenError) as exc:
        logger.warning(f"Could not park an overflowing reply: {exc}")
        return False
    await request.respond(
        b"",
        headers={
            overflow.REPLY_HEADER: transfer_id,
            overflow.SIZE_HEADER: str(len(payload)),
        },
    )
    return True


def _stream_frames(
    exchange: Callable[[Any, Any], Any], transfer_id: str
) -> Iterator[bytes]:
    sequence, frame = 0, bytearray()
    while True:
        reply = exchange(
            transfer_pb.ReadRequest(id=transfer_id, sequence=sequence),
            transfer_pb.ReadResponse,
        )
        if reply.sequence != sequence:
            raise NatsRPCError("INTERNAL", "Stream sequence mismatch")
        if reply.done:
            if frame:
                raise NatsRPCError("INTERNAL", "Stream ended mid-frame")
            return
        if reply.pending:
            time.sleep(0.02)
            continue
        sequence += 1
        frame.extend(reply.data)
        if reply.frame_end:
            yield bytes(frame)
            frame.clear()


def _announced_size(headers: Any) -> int:
    # Only bounds the wait; _download_async rejects a malformed size itself.
    try:
        return max(0, int(headers.get(overflow.SIZE_HEADER, "")))
    except ValueError:
        return 0


class _Reply:
    """A reassembled overflow reply, shaped like a NATS message."""

    def __init__(self, data: bytes, headers: dict[str, str] | None) -> None:
        self.data, self.headers = data, headers


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
        # Protect loop lifecycle and token bookkeeping, never network waits.
        # Connection initialization is serialized separately on the owning loop.
        self._call_lock = RLock()
        self._connect_lock: asyncio.Lock | None = None

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
        with self._call_lock:
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
        self._connect_lock = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5.0)

    async def _ensure_connection_async(self) -> NATSClient:
        if self._connect_lock is None:
            self._connect_lock = asyncio.Lock()
        async with self._connect_lock:
            if self._nc is not None and not self._nc.is_closed:
                return self._nc
            nc = NATSClient()
            try:
                await nc.connect(
                    self._nats_url,
                    pending_size=0,
                    name=connection_name(
                        rpc_client_role(self._service_identity, type(self))
                    ),
                )
            except BaseException:
                await nc.close()
                raise
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
        self,
        subject: str,
        request: Message,
        response_cls: type[_ResponseT],
        *,
        transfer: TransferTrace | None = None,
    ) -> _ResponseT:
        payload = request.SerializeToString()
        with self._call_lock:
            token = self._current_token()
        headers = {self._auth_header: token}
        # The span starts in the calling thread, whose context holds the parent
        # (e.g. a request handler); the trace travels in the headers.
        with client_span(
            subject, headers, size=len(payload), transfer=transfer
        ) as span:
            if transfer is not None:  # a transfer's own chunk: always small
                return self._rpc_parse(
                    self._rpc_request(subject, payload, headers), response_cls, transfer
                )
            headers[overflow.ACCEPT_HEADER] = "1"
            trace = TransferTrace(span)
            chunk = self._chunk_call(token, trace)
            upload = None
            try:
                try:
                    msg = self._rpc_request(subject, payload, headers)
                except NatsRPCPayloadTooLargeError as exc:
                    if not exc.unsent:
                        raise
                    upload = self._run_coro(
                        self._upload_async(chunk, payload, exc),
                        timeout=self._overflow_timeout(len(payload)),
                    )
                    msg = self._rpc_request(
                        subject, b"", {**headers, overflow.REQUEST_HEADER: upload}
                    )
                reply_headers = msg.headers or {}
                if overflow.REPLY_HEADER in reply_headers and not (
                    ERROR_HEADER in reply_headers or ERROR_CODE_HEADER in reply_headers
                ):
                    record_reply(len(msg.data or b""))
                    data = self._run_coro(
                        self._download_async(chunk, reply_headers),
                        timeout=self._overflow_timeout(_announced_size(reply_headers)),
                    )
                    msg = _Reply(data, None)
                return self._rpc_parse(msg, response_cls, None)
            finally:
                if upload is not None:
                    self._close_overflow(chunk, upload)
                record_overflow(trace)

    def _rpc_request(
        self, subject: str, payload: bytes, headers: dict[str, str]
    ) -> Any:
        return self._run_coro(
            asyncio.wait_for(
                self._do_request_async(subject, payload, headers),
                timeout=self._timeout_seconds,
            )
        )

    @staticmethod
    def _rpc_parse(
        msg: Any, response_cls: type[_ResponseT], transfer: TransferTrace | None
    ) -> _ResponseT:
        record_reply(len(msg.data or b""), transfer=transfer)
        reply_headers = msg.headers or {}
        if ERROR_HEADER in reply_headers or ERROR_CODE_HEADER in reply_headers:
            code = reply_headers.get(ERROR_CODE_HEADER, "UNKNOWN")
            record_error(code)
            raise NatsRPCError(
                code, reply_headers.get(ERROR_HEADER, "remote service error")
            )

        response = response_cls()
        response.ParseFromString(msg.data)
        if response.HasField("error"):
            error = _call_error(response)
            record_error(error.code, error.message)
            if error.code == "PAYLOAD_TOO_LARGE":
                raise NatsRPCPayloadTooLargeError(error.message)
        return response

    # ------------------------------------------------------------------
    # Overflow: payloads above the broker limit travel as transfer frames
    # (naas_abi_sdk.overflow, docs/adr/20261003_nats-rpc-overflow.md).
    # ------------------------------------------------------------------

    def _chunk_call(self, token: str, trace: TransferTrace) -> overflow.Call:
        """One overflow exchange, counted on the call's span (``trace``)."""

        async def call(subject: str, request: Any, response_cls: Any) -> Any:
            request.context.CopyFrom(self._context())
            payload = request.SerializeToString()
            headers = {self._auth_header: token}
            with client_span(subject, headers, size=len(payload), transfer=trace):
                msg = await asyncio.wait_for(
                    self._do_request_async(subject, payload, headers),
                    timeout=self._timeout_seconds,
                )
            record_reply(len(msg.data or b""), transfer=trace)
            response = response_cls.FromString(msg.data)
            if response.HasField("error"):
                raise NatsRPCError(response.error.code, response.error.message)
            return response

        return call

    def _overflow_timeout(self, size: int) -> float:
        # Each exchange has its own deadline; this only bounds the sync wait.
        return self._timeout_seconds * (size // overflow.MIN_CHUNK_BYTES + 4)

    async def _upload_async(
        self,
        chunk: overflow.Call,
        payload: bytes,
        refused: NatsRPCPayloadTooLargeError,
    ) -> str:
        nc = await self._ensure_connection_async()
        limit = nc.max_payload
        if not overflow.possible(limit):
            raise refused
        try:
            return await overflow.upload(
                chunk, payload, chunk_bytes=overflow.chunk_size(limit)
            )
        except NoRespondersError:  # an engine without overflow
            raise refused from None
        except overflow.OverflowRefused as exc:
            raise NatsRPCPayloadTooLargeError(str(exc)) from exc

    async def _download_async(self, chunk: overflow.Call, reply_headers: Any) -> bytes:
        transfer_id = reply_headers[overflow.REPLY_HEADER]
        try:
            size = int(reply_headers.get(overflow.SIZE_HEADER, ""))
        except ValueError:
            await overflow.close(chunk, transfer_id)
            raise NatsRPCError(
                "INTERNAL", "Overflowed reply without a valid size"
            ) from None
        try:
            return await overflow.download(chunk, transfer_id, size)
        except overflow.OverflowRefused as exc:
            if exc.code == "PAYLOAD_TOO_LARGE":
                raise NatsRPCPayloadTooLargeError(str(exc)) from exc
            raise NatsRPCError(exc.code, str(exc)) from exc

    # ------------------------------------------------------------------
    # Streamed reads: a domain's transfer/v1 stream, read as the caller
    # iterates (docs/adr/20261003_nats-streamed-results.md).
    # ------------------------------------------------------------------

    @contextmanager
    def _transfer_stream(
        self,
        prefix: str,
        operation: str,
        metadata: bytes,
        raise_error: Callable[[Any], None],
    ) -> Iterator[Iterator[bytes] | None]:
        """Yield the frames of one stream, or ``None`` when no host answers the
        open (an engine without it: use the unary call). ``raise_error`` raises
        the domain's exception for an error reply. Leaving closes the session."""
        # One span for the whole stream (totals as attributes), not one per frame.
        with transfer_span(prefix, operation) as trace:
            nc = self._run_coro(self._ensure_connection_async())

            def exchange(request: Any, response_cls: Any) -> Any:
                name = type(request).__name__.removesuffix("Request").lower()
                request.context.CopyFrom(self._context())
                response = self._call(
                    transfer_subject(prefix, name, getattr(request, "id", "")),
                    request,
                    response_cls,
                    transfer=trace,
                )
                if response.HasField("error"):
                    raise_error(response.error)
                return response

            try:
                opened = exchange(
                    transfer_pb.OpenRequest(
                        operation=operation,
                        metadata=metadata,
                        chunk_bytes=min(1024 * 1024, nc.max_payload // 2),
                    ),
                    transfer_pb.OpenResponse,
                )
            except NoRespondersError:
                yield None
                return
            try:
                exchange(
                    transfer_pb.StartRequest(id=opened.id), transfer_pb.StartResponse
                )
                yield _stream_frames(exchange, opened.id)
            finally:
                try:
                    exchange(
                        transfer_pb.CloseRequest(id=opened.id),
                        transfer_pb.CloseResponse,
                    )
                except Exception as exc:  # noqa: BLE001 - idle expiry releases it
                    logger.warning(f"Stream cleanup failed: {type(exc).__name__}")

    def _close_overflow(self, chunk: overflow.Call, transfer_id: str) -> None:
        try:
            self._run_coro(
                overflow.close(chunk, transfer_id),
                timeout=self._timeout_seconds + 1.0,
            )
        except Exception:  # noqa: BLE001 - idle expiry releases it
            logger.opt(exception=True).warning("Could not close an overflow upload")

    async def _do_request_async(
        self, subject: str, payload: bytes, headers: dict[str, str]
    ):
        nc = await self._ensure_connection_async()
        # NATS counts the HPUB header block as part of the message size. nats-py's
        # publish check only counts the body, so check both before sending.
        header_size = len(b"NATS/1.0\r\n\r\n") + sum(
            len(f"{key}: {value}\r\n".encode()) for key, value in headers.items()
        )
        limit = nc.max_payload
        if len(payload) + header_size > limit:
            raise NatsRPCPayloadTooLargeError(
                f"Request exceeds {limit} bytes including headers; "
                "use streaming or a storage reference.",
                unsent=True,
            )
        try:
            return await nc.request(
                subject, payload, timeout=self._timeout_seconds, headers=headers
            )
        except MaxPayloadError as exc:
            raise NatsRPCPayloadTooLargeError(
                "Request exceeds the server payload limit; use streaming or a storage reference.",
                unsent=True,
            ) from exc
