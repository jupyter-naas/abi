"""Engine side of RPC overflow: payloads above the broker limit.

One ``OverflowHost`` per process, on ``abi.rpc.overflow``, started with the NATS
primaries. ``respond_protobuf`` parks a reply that does not fit (``park``);
``request_payload`` reads a request the client uploaded first (``fetch``). The
client side and the headers are in ``naas_abi_sdk.overflow``. See
docs/adr/20261003_nats-rpc-overflow.md.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from naas_abi_core.engine.nats_auth import verify_service_token
from naas_abi_core.engine.nats_transfer import (
    TransferError,
    TransferHost,
    TransferSession,
    stream_thread,
)
from naas_abi_sdk import overflow
from naas_abi_sdk.telemetry import serve_transfer
from naas_abi_sdk.transfer import Transfer
from nats.errors import NoRespondersError

AUTH_HEADER = "Nats-Auth-Token"
_TRACE_HEADERS = ("traceparent", "tracestate")
_FETCH_TIMEOUT_SECONDS = 10.0


@dataclass
class _ParkedSession(TransferSession):
    parked: int = 0


async def _echo(operation: str, metadata: bytes, source: Any):
    """Serve the stored bytes back: a parked reply, or an upload to its service."""
    if source is None:
        return
    while True:
        data = await stream_thread(source.read, overflow.CHUNK_BYTES)
        if not data:
            return
        yield data


class OverflowHost(TransferHost):
    def __init__(
        self,
        secret: str,
        *,
        max_value_bytes: int = overflow.MAX_VALUE_BYTES,
        max_parked_bytes: int = 1024 * 1024 * 1024,
        max_buffered_upload_bytes: int = 1024 * 1024 * 1024,
        chunk_bytes: int = overflow.CHUNK_BYTES,
        idle_seconds: float = 60.0,
        max_sessions: int = 64,
    ) -> None:
        super().__init__(
            overflow.PREFIX,
            secret,
            _echo,
            operations=(overflow.UPLOAD_OPERATION,),
            chunk_bytes=chunk_bytes,
            idle_seconds=idle_seconds,
            max_sessions=max_sessions,
            max_upload_bytes=max_value_bytes,
            max_buffered_upload_bytes=max_buffered_upload_bytes,
        )
        self.max_value_bytes = max_value_bytes
        self.max_parked_bytes = max_parked_bytes
        self.parked_bytes = 0
        self._nc: Any = None

    async def start(self, nc: Any) -> None:
        await super().start(nc)
        self._nc = nc

    async def stop(self) -> None:
        uninstall(self)
        await super().stop()

    def accepts(self, size: int) -> bool:
        return size <= self.max_value_bytes

    async def park(self, headers: Mapping[str, str], data: bytes) -> str:
        """Hold a reply for the request's caller; return its transfer id."""
        caller = verify_service_token(headers.get(AUTH_HEADER, ""), self.secret)
        if len(data) > self.max_value_bytes:
            raise TransferError(
                "PAYLOAD_TOO_LARGE", "Reply exceeds the overflow value limit"
            )
        if self.parked_bytes + len(data) > self.max_parked_bytes:
            raise TransferError("RESOURCE_EXHAUSTED", "Overflow reply budget exhausted")
        if (
            len(self.sessions) >= self.max_sessions
            or len(self.retiring) >= self.max_sessions
        ):
            raise TransferError(
                "RESOURCE_EXHAUSTED", "Transfer session capacity reached"
            )
        key = f"{self.owner}:{uuid4().hex}"
        trace = serve_transfer(
            self.prefix, "reply", dict(headers), attributes={"abi.caller": caller}
        )
        session = _ParkedSession(
            caller,
            "reply",
            b"",
            self.chunk_bytes,
            source=io.BytesIO(data),
            touched=asyncio.get_running_loop().time(),
            trace=trace,
            parked=len(data),
        )
        self.parked_bytes += len(data)
        self.sessions[key] = session
        session.task = asyncio.create_task(self._produce(session))
        return key

    async def _retire(self, session: TransferSession) -> None:
        try:
            await super()._retire(session)
        finally:
            self.parked_bytes -= getattr(session, "parked", 0)

    async def fetch(self, transfer_id: str, headers: Mapping[str, str]) -> bytes:
        """Read an uploaded request with the caller's token, then release it.

        The upload may be owned by another replica: the call reached this one
        through a queue group. The caller's token keeps the session binding.
        """
        forwarded = {AUTH_HEADER: headers.get(AUTH_HEADER, "")}
        forwarded.update({k: headers[k] for k in _TRACE_HEADERS if k in headers})

        async def call(subject: str, request: Any, response_type: Any) -> Any:
            request.context.timeout_ms = int(_FETCH_TIMEOUT_SECONDS * 1000)
            try:
                reply = await self._nc.request(
                    subject,
                    request.SerializeToString(),
                    headers=forwarded,
                    timeout=_FETCH_TIMEOUT_SECONDS,
                )
            except NoRespondersError as exc:
                raise TransferError(
                    "NOT_FOUND", "The overflow upload's owner is gone"
                ) from exc
            response = response_type.FromString(reply.data)
            if response.HasField("error"):
                raise TransferError(response.error.code, response.error.message)
            return response

        if self._nc is None:
            raise TransferError("UNAVAILABLE", "Overflow host is not started")
        transfer = Transfer(call, self.prefix, transfer_id, 0)
        try:
            await transfer.start()
            data = bytearray()
            async for fragment, _ in transfer.fragments():
                data.extend(fragment)
                if len(data) > self.max_value_bytes:
                    raise TransferError(
                        "PAYLOAD_TOO_LARGE", "Request exceeds the overflow value limit"
                    )
            return bytes(data)
        finally:
            await overflow.close(call, transfer_id)


_current: OverflowHost | None = None


def install(host: OverflowHost) -> None:
    """Make ``host`` this process's overflow host (the engine's NATS loader)."""
    global _current
    _current = host


def uninstall(host: OverflowHost) -> None:
    global _current
    if _current is host:
        _current = None


def current() -> OverflowHost | None:
    return _current
