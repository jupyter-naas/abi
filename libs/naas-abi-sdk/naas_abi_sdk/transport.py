"""One-attempt protobuf RPC. A timeout can hide a completed remote mutation."""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

from google.protobuf.message import Message
from nats.aio.client import Client
from nats.errors import MaxPayloadError, NoRespondersError

from naas_abi_sdk import no_responders, overflow
from naas_abi_sdk.call_context import current_call_context, on_behalf_of_header
from naas_abi_sdk.credentials import (
    HOST_AUDIENCE,
    NATS_AUDIENCE,
    RENEW_CONNECTION_SECONDS,
    SERVICE_KEY_PREFIX,
    ServiceKey,
)
from naas_abi_sdk.lifeline import Lifeline
from naas_abi_sdk.messages import message_size
from naas_abi_sdk.telemetry import (
    TransferTrace,
    client_span,
    record_error,
    record_overflow,
    record_reply,
)

logger = logging.getLogger(__name__)

Response = TypeVar("Response", bound=Message)

# Subjects module hosts serve (agents, models, apps). A call to one carries a
# token addressed to hosts, never the caller's own: the host reads it, and may
# forward it to discovery, but kernel services refuse it.
HOST_SUBJECT_PREFIXES = ("abi.agent.", "abi.mod.")


class RPCError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, response: Message | None = None
    ) -> None:
        self.code = code
        self.response = response
        super().__init__(f"{code}: {message}")


class NoHostTokenError(RuntimeError):
    """A transport holding a bare token was asked to call a module host."""


class Transport:
    """Async transport owned by one client/event loop.

    ``token`` is a service key (``abi_sk_...``, or a ``ServiceKey``): the
    connection logs in with it and calls carry the tokens it is exchanged
    for. A process of the engine passes its own tokens instead: a string,
    or a callable returning one.
    """

    def __init__(
        self,
        url: str,
        token: str | Callable[[], str] | ServiceKey,
        timeout: float = 10.0,
        *,
        forward_user: bool = False,
        renew_seconds: float = RENEW_CONNECTION_SECONDS,
        host_token: str | Callable[[], str] | None = None,
        **connection_options: Any,
    ) -> None:
        """``forward_user``: send the user the current call acts for
        (``Abi-On-Behalf-Of``). Only for a transport holding a trusted
        identity (``api``, ``engine``) that calls kernel services: they
        refuse the header from anyone else, and no module host needs it.

        ``host_token``: the token a call to a module host carries
        (``abi:host``), for a transport given a token instead of a key: a key
        buys one itself. Without one such a transport makes no call to a host:
        its own token must never reach one.

        ``renew_seconds``: a connection logged in with a service key
        reconnects this often, so the broker computes its subjects again
        before its own expire (they last minutes, ``credentials``)."""
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        if isinstance(token, str) and token.startswith(SERVICE_KEY_PREFIX):
            token = ServiceKey(token)
        self.credentials = token if isinstance(token, ServiceKey) else None
        if self.credentials is not None:
            with_login = "@" in url.split("//", 1)[-1]  # the URL carries its own
            for option, value in self.credentials.connect_options().items():
                if with_login and option in ("user", "password"):
                    continue
                connection_options.setdefault(option, value)
        self.url, self.token, self.timeout = url, token, timeout
        self.host_token = host_token
        self.forward_user = forward_user
        self.options = connection_options
        self.connection = Client()
        self._lock = asyncio.Lock()
        self._connected = False
        self._closed = False
        self._lifeline: Lifeline | None = None
        self.renew_seconds = renew_seconds
        self._renewal: asyncio.Task | None = None

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
                if self.credentials is not None and self.renew_seconds > 0:
                    self._renewal = asyncio.create_task(self._renew(connection))
            connection = self.connection
        # A renewal in progress (a few milliseconds): wait for it rather than
        # fail the call that happens to start then.
        deadline = asyncio.get_running_loop().time() + self.timeout
        while connection.is_reconnecting and (
            asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(0.01)
        return connection

    async def _renew(self, connection: Client) -> None:
        """Reconnect ``connection`` every ``renew_seconds``: nats-py keeps its
        subscriptions, and the broker's auth callout answers again, with the
        subjects the account's policy allows now. A revoked key, a suspended
        account or a narrowed policy ends here at the latest when the
        permissions the broker gave the connection do."""
        while True:
            await asyncio.sleep(self.renew_seconds)
            if self._closed or connection is not self.connection:
                return
            try:
                await connection.force_reconnect()
            except Exception:  # nats-py retries; the lifeline reports a loss
                logger.warning("Could not renew the broker connection", exc_info=True)

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

    async def access_token(self, audience: str = NATS_AUDIENCE) -> str:
        """The token calls carry: the key's, exchanged as needed, else the
        one this transport was given. ``audience``: ``abi:host`` for a call
        to a module host."""
        if self.credentials is not None:
            return await self.credentials.access_token(self, audience)
        if audience == HOST_AUDIENCE:
            if self.host_token is None:
                raise NoHostTokenError(
                    "This transport holds no host token: it cannot call a module "
                    "host without handing it a token the kernel services accept"
                )
            source = self.host_token
        else:
            source = self.token
        return cast(str, source() if callable(source) else source)

    async def reconnect(self) -> None:
        """Replace the connection: the broker computes the new one's
        permissions again (after a manifest approval). Subscriptions of the
        old connection are not carried over."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("Client is closed")
            self._stop_renewal()
            old, watched = self.connection, self._lifeline
            connected = self._connected
            self.connection, self._connected, self._lifeline = Client(), False, None
        if connected:
            if watched is not None:
                await watched.close(old)
            else:
                await old.close()
        await self.connect()

    def _stop_renewal(self) -> None:
        renewal, self._renewal = self._renewal, None
        if renewal is not None and renewal is not asyncio.current_task():
            renewal.cancel()

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            self._stop_renewal()
            if self._connected:
                if self._lifeline is not None:
                    await self._lifeline.close(self.connection)
                else:
                    await self.connection.close()

    async def auth_headers(
        self, current: Any = None, *, host: bool = False
    ) -> dict[str, str]:
        """This transport's credentials for a message it sends itself: its
        token (a service key's, exchanged as needed), and the current call's
        user when it forwards users. ``host``: for a message a module host will
        read, so the token is addressed to hosts."""
        token = await self.access_token(HOST_AUDIENCE if host else NATS_AUDIENCE)
        if not token or "\r" in token or "\n" in token:
            raise ValueError("A nonempty service token without newlines is required")
        headers = {"Nats-Auth-Token": token}
        if self.forward_user:
            headers.update(
                on_behalf_of_header(
                    current if current is not None else current_call_context()
                )
            )
        return headers

    async def call(
        self,
        subject: str,
        request: Message,
        response_type: type[Response],
        *,
        transfer: TransferTrace | None = None,
    ) -> Response:
        # Copy so concurrent calls never mutate a caller-owned request.
        outgoing = type(request)()
        outgoing.CopyFrom(request)
        context = cast(Any, outgoing).context
        current = current_call_context()
        if not context.trace_id:
            context.trace_id = current.trace_id or str(uuid.uuid4())
        if not context.workspace_id and current.workspace_id:
            context.workspace_id = current.workspace_id
        context.timeout_ms = int(self.timeout * 1000)
        headers = await self.auth_headers(
            current, host=subject.startswith(HOST_SUBJECT_PREFIXES)
        )
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
