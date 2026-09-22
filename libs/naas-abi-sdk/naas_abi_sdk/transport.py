"""One-attempt protobuf RPC. A timeout can hide a completed remote mutation."""

from __future__ import annotations

import asyncio
import math
import uuid
from collections.abc import Callable
from typing import Any, TypeVar, cast

from google.protobuf.message import Message
from nats.aio.client import Client
from nats.errors import MaxPayloadError

Response = TypeVar("Response", bound=Message)
MAX_PAYLOAD = 8 * 1024 * 1024


class RPCError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, response: Message | None = None
    ) -> None:
        self.code = code
        self.response = response
        super().__init__(f"{code}: {message}")


class Transport:
    """Async transport owned by one client/event loop; accepts issued tokens only."""

    def __init__(
        self,
        url: str,
        token: str | Callable[[], str],
        timeout: float = 10.0,
        **connection_options: Any,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self.url, self.token, self.timeout = url, token, timeout
        self.options = connection_options
        self.connection = Client()
        self._lock = asyncio.Lock()
        self._connected = False
        self._closed = False

    async def connect(self) -> Client:
        async with self._lock:
            if self._closed:
                raise RuntimeError("Client is closed")
            if not self._connected:
                try:
                    await self.connection.connect(
                        self.url, **self.options, pending_size=0
                    )
                except BaseException:
                    await self.connection.close()
                    self.connection = Client()
                    raise
                self._connected = True
            return self.connection

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            if self._connected:
                await self.connection.close()

    async def call(
        self, subject: str, request: Message, response_type: type[Response]
    ) -> Response:
        # Copy so concurrent calls never mutate a caller-owned request.
        outgoing = type(request)()
        outgoing.CopyFrom(request)
        context = cast(Any, outgoing).context
        if not context.trace_id:
            context.trace_id = str(uuid.uuid4())
        context.timeout_ms = int(self.timeout * 1000)
        token = self.token() if callable(self.token) else self.token
        if not token or "\r" in token or "\n" in token:
            raise ValueError("A nonempty service token without newlines is required")
        headers = {"Nats-Auth-Token": token}
        payload = outgoing.SerializeToString()

        async def send():
            nc = await self.connect()
            size = len(payload) + len(
                f"NATS/1.0\r\nNats-Auth-Token: {token}\r\n\r\n".encode()
            )
            if size > min(nc.max_payload, MAX_PAYLOAD):
                raise RPCError("PAYLOAD_TOO_LARGE", "Request exceeds broker limit")
            try:
                return await nc.request(
                    subject, payload, headers=headers, timeout=self.timeout
                )
            except MaxPayloadError as exc:
                raise RPCError(
                    "PAYLOAD_TOO_LARGE", "Request exceeds broker limit"
                ) from exc

        reply = await asyncio.wait_for(send(), timeout=self.timeout)
        h = reply.headers or {}
        if "Nats-Service-Error" in h or "Nats-Service-Error-Code" in h:
            raise RPCError(
                h.get("Nats-Service-Error-Code", "UNKNOWN"),
                h.get("Nats-Service-Error", "Remote error"),
            )
        response = response_type.FromString(reply.data)
        if response.HasField("error"):
            error = cast(Any, response).error
            while "error" in error.DESCRIPTOR.fields_by_name:
                error = error.error
            raise RPCError(error.code, error.message, response=response)
        return response
