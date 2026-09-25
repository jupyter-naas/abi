"""Bounded NATS packet transport for domain-owned streaming operations.

Inputs spool to temporary disk. Only an explicit start calls the domain handler;
closing an incomplete upload cannot modify its destination. No durable replay.
"""

from __future__ import annotations

import asyncio
import math
import tempfile
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from uuid import uuid4

from google.protobuf.message import DecodeError
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb

OPERATIONS = {
    "open": (pb.OpenRequest, pb.OpenResponse),
    "write": (pb.WriteRequest, pb.WriteResponse),
    "start": (pb.StartRequest, pb.StartResponse),
    "read": (pb.ReadRequest, pb.ReadResponse),
    "close": (pb.CloseRequest, pb.CloseResponse),
}


class TransferError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class TransferSession:
    caller: str
    operation: str
    metadata: bytes
    chunk_bytes: int
    source: Any = None
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=2))
    task: Any = None
    error: Any = None
    upload_sequence: int = 0
    read_sequence: int = 0
    uploaded: int = 0
    touched: float = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


async def stream_thread(function, *args):
    """Do not close a stream while synchronous backend code still uses it."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            if task.cancelled():
                raise
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError()
    return result


class TransferHost:
    def __init__(
        self,
        prefix,
        secret,
        handler,
        *,
        operations,
        chunk_bytes=64 * 1024,
        idle_seconds=60.0,
        max_sessions=32,
        max_upload_bytes=None,
        total_seconds=None,
        max_buffered_upload_bytes=None,
        close_timeout_seconds=1.0,
        error_mapper=None,
    ):
        if not math.isfinite(idle_seconds) or idle_seconds <= 0:
            raise ValueError("Transfer idle timeout must be positive and finite")
        if total_seconds is not None and (
            not math.isfinite(total_seconds) or total_seconds <= 0
        ):
            raise ValueError("Transfer deadline must be positive and finite")
        if (
            chunk_bytes < 1024
            or max_sessions < 1
            or (max_upload_bytes is not None and max_upload_bytes < 1)
            or (max_buffered_upload_bytes is not None and max_buffered_upload_bytes < 1)
        ):
            raise ValueError("Invalid transfer capacity")
        if close_timeout_seconds <= 0 or not math.isfinite(close_timeout_seconds):
            raise ValueError("Close timeout must be positive and finite")
        self.close_timeout_seconds = close_timeout_seconds
        self.max_buffered_upload_bytes = max_buffered_upload_bytes
        self.buffered_upload_bytes = 0
        self.retiring: set[asyncio.Task] = set()
        self.prefix, self.secret, self.handler = prefix, secret, handler
        self.owner = uuid4().hex
        self.operations, self.chunk_bytes = set(operations), chunk_bytes
        self.idle_seconds, self.max_sessions = idle_seconds, max_sessions
        self.max_upload_bytes, self.total_seconds = max_upload_bytes, total_seconds
        self.error_mapper = error_mapper
        self.sessions: dict[str, TransferSession] = {}
        self.subscriptions: list[Any] = []
        self.tasks: set[asyncio.Task] = set()
        self.reaper = None
        self.packet_bytes = 0

    async def start(self, nc):
        self.packet_bytes = min(nc.max_payload, 8 * 1024 * 1024)
        self.chunk_bytes = min(self.chunk_bytes, self.packet_bytes // 2)
        if self.chunk_bytes < 1024:
            raise ValueError("Broker payload is too small for transfers")
        try:
            for operation in OPERATIONS:
                self.subscriptions.append(
                    await nc.subscribe(
                        f"{self.prefix}.{operation}",
                        queue=f"{self.prefix}.owners" if operation == "open" else "",
                        cb=partial(self._dispatch, operation),
                    )
                )
            for operation in OPERATIONS.keys() - {"open"}:
                self.subscriptions.append(
                    await nc.subscribe(
                        f"{self.prefix}.{self.owner}.{operation}",
                        cb=partial(self._dispatch, operation),
                    )
                )
            await nc.flush()
            self.reaper = asyncio.create_task(self._expire())
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        for sub in self.subscriptions:
            await sub.unsubscribe()
        self.subscriptions.clear()
        if self.reaper:
            self.reaper.cancel()
            await asyncio.gather(self.reaper, return_exceptions=True)
        for task in self.tasks:
            task.cancel()
        for key in list(self.sessions):
            self._begin_close(key)
        pending = self.tasks | self.retiring
        if pending:
            await asyncio.wait(pending, timeout=self.close_timeout_seconds)

    async def _expire(self):
        while True:
            await asyncio.sleep(min(1, self.idle_seconds))
            now = asyncio.get_running_loop().time()
            expired = [
                key
                for key, value in self.sessions.items()
                if not value.lock.locked() and now - value.touched > self.idle_seconds
            ]
            for key in expired:
                self._begin_close(key)

    def _begin_close(self, key):
        session = self.sessions.pop(key, None)
        if session is None:
            return None
        task = asyncio.create_task(self._retire(session))
        self.retiring.add(task)
        task.add_done_callback(self.retiring.discard)
        task.add_done_callback(self._observe_cleanup)
        return task

    @staticmethod
    def _observe_cleanup(task):
        if not task.cancelled() and task.exception():
            logger.opt(exception=task.exception()).error("Transfer cleanup failed")

    async def _retire(self, session):
        # Keep the file alive until every synchronous user has stopped. A blocked
        # backend must not hold the expiry loop or the public session slot.
        async with session.lock:
            try:
                if session.task:
                    session.task.cancel()
                    await asyncio.gather(session.task, return_exceptions=True)
            finally:
                if session.source is not None:
                    session.source.close()
                self.buffered_upload_bytes -= session.uploaded

    async def _close(self, key):
        task = self._begin_close(key)
        if task:
            done, _ = await asyncio.wait({task}, timeout=self.close_timeout_seconds)
            if not done:
                logger.warning("Transfer cleanup deferred until backend returns")

    async def _dispatch(self, operation, msg):
        if operation != "open":
            try:
                transfer_id = OPERATIONS[operation][0].FromString(msg.data).id
            except DecodeError:
                transfer_id = ""
            # Compatibility subjects fan out; only the encoded owner may reply.
            if ":" in transfer_id and transfer_id.split(":", 1)[0] != self.owner:
                return
        if len(self.tasks) >= self.max_sessions * 4:
            response = OPERATIONS[operation][1]()
            response.error.code, response.error.message = (
                "RESOURCE_EXHAUSTED",
                "Transfer request capacity reached",
            )
            if msg.reply:
                await msg.respond(response.SerializeToString())
            return
        task = asyncio.create_task(self._handle(operation, msg))
        self.tasks.add(task)
        task.add_done_callback(self._finished)

    def _finished(self, task):
        self.tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.error("Transfer reply failed: {}", type(task.exception()).__name__)

    def _error(self, exc):
        if isinstance(exc, TransferError):
            return exc.code, str(exc)
        if isinstance(exc, InvalidServiceTokenError):
            return "UNAUTHENTICATED", "Invalid service token"
        if isinstance(exc, asyncio.TimeoutError):
            return "DEADLINE_EXCEEDED", "Configured operation deadline exceeded"
        if self.error_mapper:
            mapped = self.error_mapper(exc)
            if mapped:
                return mapped
        if isinstance(exc, (ValueError, TypeError, DecodeError)):
            return "INVALID_ARGUMENT", "Invalid transfer or operation payload"
        logger.opt(exception=exc).error("Unexpected transfer failure")
        return "INTERNAL", "Streaming operation failed"

    async def _handle(self, operation, msg):
        response = OPERATIONS[operation][1]()
        try:
            caller = verify_service_token(
                (msg.headers or {}).get("Nats-Auth-Token", ""), self.secret
            )
            if len(msg.data) > self.packet_bytes:
                raise TransferError(
                    "PAYLOAD_TOO_LARGE", "Transfer packet exceeds broker limit"
                )
            request = OPERATIONS[operation][0].FromString(msg.data)
            response = await self._execute(operation, request, caller)
        except Exception as exc:  # noqa: BLE001 - sanitize errors at transport boundary
            response.error.code, response.error.message = self._error(exc)
        if msg.reply:
            await msg.respond(response.SerializeToString())

    async def _produce(self, session):
        async def consume():
            iterator = self.handler(session.operation, session.metadata, session.source)
            try:
                async for frame in iterator:
                    if not isinstance(frame, bytes):
                        raise TypeError("Transfer handlers must yield bytes")
                    for offset in range(0, max(1, len(frame)), session.chunk_bytes):
                        data = frame[offset : offset + session.chunk_bytes]
                        await session.queue.put(
                            (data, offset + session.chunk_bytes >= len(frame))
                        )
            finally:
                await iterator.aclose()

        try:
            if self.total_seconds is None:
                await consume()
            else:
                await asyncio.wait_for(consume(), self.total_seconds)
        except Exception as exc:  # noqa: BLE001 - delivered on the next read
            # Record failures even if the caller has abandoned the transfer.
            session.error = TransferError(*self._error(exc))

    async def _execute(self, operation, request, caller):
        now = asyncio.get_running_loop().time()
        if operation == "open":
            if (
                request.operation not in self.operations
                or len(request.metadata) > 16 * 1024
            ):
                raise ValueError("Unsupported operation or oversized metadata")
            if (
                len(self.sessions) >= self.max_sessions
                or len(self.retiring) >= self.max_sessions
            ):
                raise TransferError(
                    "RESOURCE_EXHAUSTED", "Transfer session capacity reached"
                )
            size = min(request.chunk_bytes or self.chunk_bytes, self.chunk_bytes)
            if size < 1024:
                raise ValueError("Chunk size is too small")
            key = f"{self.owner}:{uuid4().hex}"
            self.sessions[key] = TransferSession(
                caller, request.operation, request.metadata, size, touched=now
            )
            return pb.OpenResponse(id=key, chunk_bytes=size)
        session = self.sessions.get(request.id)
        if session is None:
            if operation == "close":
                return pb.CloseResponse()
            raise TransferError("NOT_FOUND", "Transfer expired or closed")
        if session.caller != caller:
            raise TransferError(
                "PERMISSION_DENIED", "Transfer belongs to another caller"
            )
        session.touched = now
        if operation == "close":
            await self._close(request.id)
            return pb.CloseResponse()
        if session.lock.locked():
            raise TransferError(
                "CONFLICT", "Concurrent transfer operations are not allowed"
            )
        async with session.lock:
            if operation == "write":
                if session.task or request.sequence != session.upload_sequence:
                    raise TransferError("CONFLICT", "Invalid upload state or sequence")
                if len(request.data) > session.chunk_bytes:
                    raise TransferError(
                        "PAYLOAD_TOO_LARGE", "Upload chunk exceeds negotiated size"
                    )
                if (
                    self.max_upload_bytes is not None
                    and session.uploaded + len(request.data) > self.max_upload_bytes
                ):
                    raise TransferError(
                        "PAYLOAD_TOO_LARGE", "Configured total upload limit exceeded"
                    )
                if (
                    self.max_buffered_upload_bytes is not None
                    and self.buffered_upload_bytes + len(request.data)
                    > self.max_buffered_upload_bytes
                ):
                    raise TransferError(
                        "RESOURCE_EXHAUSTED", "Total upload budget exhausted"
                    )
                if session.source is None:
                    session.source = tempfile.TemporaryFile()
                # Reserve before yielding, including while a write is in flight.
                self.buffered_upload_bytes += len(request.data)
                session.uploaded += len(request.data)
                await stream_thread(session.source.write, request.data)
                session.upload_sequence += 1
                return pb.WriteResponse()
            if operation == "start":
                if session.task:
                    raise TransferError(
                        "CONFLICT", "Transfer already started; do not replay"
                    )
                if session.source is not None:
                    session.source.seek(0)
                session.task = asyncio.create_task(self._produce(session))
                return pb.StartResponse()
            if not session.task or request.sequence != session.read_sequence:
                raise TransferError("CONFLICT", "Invalid read state or sequence")
            if session.queue.empty() and not session.task.done():
                # Event-driven long poll, bounded below the caller's RPC deadline.
                budget = min(
                    0.5, self.idle_seconds / 2, request.context.timeout_ms / 2000
                )
                if budget > 0:
                    waiting = asyncio.create_task(session.queue.get())
                    try:
                        await asyncio.wait(
                            (waiting, session.task),
                            timeout=budget,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if waiting.done():
                            data, end = waiting.result()
                            response = pb.ReadResponse(
                                data=data, frame_end=end, sequence=session.read_sequence
                            )
                            session.read_sequence += 1
                            return response
                    finally:
                        waiting.cancel()
                        await asyncio.gather(waiting, return_exceptions=True)
            if session.queue.empty():
                if session.task.done():
                    if session.error:
                        raise session.error
                    return pb.ReadResponse(done=True, sequence=session.read_sequence)
                # Short bounded exchange even during minutes of model reasoning.
                return pb.ReadResponse(pending=True, sequence=session.read_sequence)
            data, end = session.queue.get_nowait()
            response = pb.ReadResponse(
                data=data, frame_end=end, sequence=session.read_sequence
            )
            session.read_sequence += 1
            return response
