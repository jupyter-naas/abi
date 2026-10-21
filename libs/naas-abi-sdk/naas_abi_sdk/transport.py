"""One-attempt protobuf RPC. A timeout can hide a completed remote mutation."""

from __future__ import annotations

import asyncio
import math
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast
from urllib.parse import urlsplit

from google.protobuf.message import Message
from nats.aio.client import Client
from nats.errors import MaxPayloadError, NoRespondersError

from naas_abi_sdk import no_responders, overflow
from naas_abi_sdk.lifeline import Lifeline
from naas_abi_sdk.messages import message_size
from naas_abi_sdk.telemetry import (
    TransferTrace,
    client_span,
    record_error,
    record_overflow,
    record_reply,
)

Response = TypeVar("Response", bound=Message)

# The broker user SDK modules log in as, and the inbox prefix their connections
# use: the user may not subscribe to _INBOX.>, where the engine's replies go
# (naas_abi_core.engine.nats_permissions).
MODULE_USER = "module"
MODULE_INBOX_PREFIX = "_INBOX_MODULES"
# Reply and stream inboxes a peer may name: the engine's, and the modules'.
INBOX_PREFIXES = ("_INBOX.", MODULE_INBOX_PREFIX + ".")


def is_inbox(subject: str) -> bool:
    return subject.startswith(INBOX_PREFIXES)


# A module instance id: one subject token, as discovery accepts it at registration
# (discovery_service._instance_id). An id with a dot could put another instance's id
# where module_audience reads it.
INSTANCE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


def is_module_subject(subject: str) -> bool:
    """Whether ``subject`` addresses a module instance (``abi.agent.<project>.
    <instance>...``, ``abi.mod.<project>.<instance>...``): the token sent there is
    bound to that instance (naas_abi_core.engine.nats_auth, "Audience")."""
    parts = subject.split(".", 2)
    return len(parts) == 3 and parts[0] == "abi" and parts[1] in ("agent", "mod")


def module_audience(subject: str, instance_id: str) -> str:
    """``instance_id``, the instance the caller means to call, once checked against
    ``subject``: a valid instance id, and the subject's whole instance token. The
    audience is the caller's, never a segment read from the subject."""
    if not INSTANCE_ID.fullmatch(instance_id):
        raise ValueError(f"Not a module instance id: {instance_id!r}")
    parts = subject.split(".")
    if len(parts) < 5 or parts[3] != instance_id:
        raise ValueError(f"{subject} does not address instance {instance_id}")
    return instance_id


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
        if urlsplit(url).username == MODULE_USER:
            self.options.setdefault("inbox_prefix", MODULE_INBOX_PREFIX)
        self.connection = Client()
        self._lock = asyncio.Lock()
        self._connected = False
        self._closed = False
        self._lifeline: Lifeline | None = None

    async def connect(self) -> Client:
        async with self._lock:
            if self._closed:
                raise RuntimeError("Client is closed")
            if not self._connected:
                connection = self.connection
                watched = Lifeline(str(self.options.get("name") or "transport"))
                try:
                    await connection.connect(
                        self.url,
                        **self.options,
                        pending_size=0,
                        closed_cb=self._on_closed(connection, watched),
                    )
                except BaseException:
                    watched.closing = True
                    await connection.close()
                    self.connection = Client()
                    raise
                self._lifeline = watched
                self._connected = True
            return self.connection

    def _on_closed(
        self, connection: Client, watched: Lifeline
    ) -> Callable[[], Awaitable[None]]:
        async def closed() -> None:
            if not watched.closing and connection is self.connection:
                # nats-py gave up reconnecting: a later call connects afresh.
                self._connected = False
                self.connection = Client()
            await watched.closed()

        return closed

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            if self._connected:
                if self._lifeline is not None:
                    await self._lifeline.close(self.connection)
                else:
                    await self.connection.close()

    def _token(self, subject: str, instance_id: str | None = None) -> str:
        if not is_module_subject(subject):
            if instance_id is not None:
                raise ValueError(f"{subject} addresses no module instance")
            return self.token() if callable(self.token) else self.token
        if instance_id is None:
            raise ValueError(
                f"A call to a module ({subject}) names the instance it calls "
                "(instance_id): its token is bound to it"
            )
        audience = module_audience(subject, instance_id)
        bind = getattr(self.token, "for_audience", None)
        if bind is None:
            raise ValueError(
                f"A call to a module ({subject}) needs a token bound to it: give the "
                "transport a token source with for_audience "
                "(naas_abi_sdk.service_token.ModuleToken, or "
                "naas_abi_core.engine.nats_auth.ServiceTokenSource)"
            )
        return bind(audience)

    async def call(
        self,
        subject: str,
        request: Message,
        response_type: type[Response],
        *,
        transfer: TransferTrace | None = None,
        instance_id: str | None = None,
    ) -> Response:
        """One exchange. ``instance_id``: the module instance a call to a module
        subject goes to, which its token is bound to (required there)."""
        # Copy so concurrent calls never mutate a caller-owned request.
        outgoing = type(request)()
        outgoing.CopyFrom(request)
        context = cast(Any, outgoing).context
        if not context.trace_id:
            context.trace_id = str(uuid.uuid4())
        context.timeout_ms = int(self.timeout * 1000)
        token = self._token(subject, instance_id)
        if not token or "\r" in token or "\n" in token:
            raise ValueError("A nonempty service token without newlines is required")
        headers = {"Nats-Auth-Token": token}
        payload = outgoing.SerializeToString()
        # The span covers the whole exchange; the trace travels in the headers.
        with client_span(
            subject, headers, size=len(payload), transfer=transfer
        ) as span:
            if transfer is not None:  # a transfer's own chunk: always small
                return await self._exchange(
                    subject, payload, headers, response_type, transfer
                )
            headers[overflow.ACCEPT_HEADER] = "1"
            return await self._overflowing(
                subject, payload, headers, response_type, TransferTrace(span)
            )

    async def _overflowing(
        self,
        subject: str,
        payload: bytes,
        headers: dict[str, str],
        response_type: type[Response],
        trace: TransferTrace,
    ) -> Response:
        """Upload a request above the broker limit first; download a parked reply.

        The overflow's chunk exchanges count on this call's span (``trace``).
        """

        async def chunk(subject: str, request: Message, response_type: type) -> Any:
            return await self.call(subject, request, response_type, transfer=trace)

        nc = await self.connect()
        limit = nc.max_payload
        upload = None
        if message_size(payload, headers) > limit and overflow.possible(limit):
            try:
                upload = await overflow.upload(
                    chunk, payload, chunk_bytes=overflow.chunk_size(limit)
                )
            except NoRespondersError as exc:  # an engine without overflow
                raise RPCError(
                    "PAYLOAD_TOO_LARGE", "Request exceeds broker limit"
                ) from exc
            except overflow.OverflowRefused as exc:
                raise RPCError(exc.code, str(exc)) from exc
            headers = {**headers, overflow.REQUEST_HEADER: upload}
            payload = b""
        try:
            return await self._exchange(
                subject, payload, headers, response_type, download=chunk
            )
        finally:
            if upload is not None:
                await overflow.close(chunk, upload)
            record_overflow(trace)

    async def _exchange(
        self,
        subject: str,
        payload: bytes,
        headers: dict[str, str],
        response_type: type[Response],
        transfer: TransferTrace | None = None,
        *,
        download: overflow.Call | None = None,
    ) -> Response:
        async def send():
            nc = await self.connect()
            if message_size(payload, headers) > nc.max_payload:
                raise RPCError("PAYLOAD_TOO_LARGE", "Request exceeds broker limit")
            try:
                # An engine handing over may leave nobody subscribed for a moment.
                # A transfer's session calls belong to one engine, so only its
                # open (on the queue group) is resent.
                resend = transfer is None or no_responders.transfer_open(subject)
                return await no_responders.request(
                    nc,
                    subject,
                    payload,
                    headers=headers,
                    timeout=self.timeout,
                    retry_seconds=no_responders.RETRY_SECONDS if resend else 0,
                )
            except MaxPayloadError as exc:
                raise RPCError(
                    "PAYLOAD_TOO_LARGE", "Request exceeds broker limit"
                ) from exc

        reply = await asyncio.wait_for(send(), timeout=self.timeout)
        record_reply(len(reply.data or b""), transfer=transfer)
        h = reply.headers or {}
        if "Nats-Service-Error" in h or "Nats-Service-Error-Code" in h:
            code = h.get("Nats-Service-Error-Code", "UNKNOWN")
            record_error(code)
            raise RPCError(code, h.get("Nats-Service-Error", "Remote error"))
        data = reply.data
        if download is not None and overflow.REPLY_HEADER in h:
            data = await _download(download, h)
            record_reply(len(data))
        response = response_type.FromString(data)
        if response.HasField("error"):
            error = cast(Any, response).error
            while "error" in error.DESCRIPTOR.fields_by_name:
                error = error.error
            record_error(error.code, error.message)
            raise RPCError(error.code, error.message, response=response)
        return response


async def _download(call: overflow.Call, headers: Any) -> bytes:
    try:
        size = int(headers.get(overflow.SIZE_HEADER, ""))
    except ValueError:
        await overflow.close(call, headers[overflow.REPLY_HEADER])
        raise RPCError("INTERNAL", "Overflowed reply without a valid size") from None
    try:
        return await overflow.download(call, headers[overflow.REPLY_HEADER], size)
    except overflow.OverflowRefused as exc:
        raise RPCError(exc.code, str(exc)) from exc
