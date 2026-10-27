"""One-attempt protobuf RPC. A timeout can hide a completed remote mutation."""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import logging
import math
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

from google.protobuf.message import Message
from nats.aio.client import Client
from nats.errors import MaxPayloadError, NoRespondersError

from naas_abi_sdk import no_responders, overflow
from naas_abi_sdk.call_context import Principal, current_call_context
from naas_abi_sdk.credentials import (
    NATS_AUDIENCE,
    RENEW_CONNECTION_SECONDS,
    SERVICE_KEY_PREFIX,
    ServiceKey,
    host_audience,
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

# Subjects module hosts serve (agents, models, apps): abi.agent.<project>.<sa>...
# and abi.mod.<project>.<sa>.... A call to one carries a token addressed to that
# host (``<sa>``), never the caller's own: the host reads it, and may forward it
# to discovery, but kernel services refuse it and discovery accepts it from
# that host only.
HOST_SUBJECT_PREFIXES = ("abi.agent.", "abi.mod.")


def host_recipient(subject: str) -> str | None:
    """The ``<sa>`` of the host a subject addresses, None for any other."""
    if not subject.startswith(HOST_SUBJECT_PREFIXES):
        return None
    parts = subject.split(".", 4)
    return parts[3] if len(parts) > 3 and parts[3] else None


class RPCError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, response: Message | None = None
    ) -> None:
        self.code = code
        self.message = message
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
        delegate: Callable[[Principal, str | None, Any], str | Awaitable[str]]
        | None = None,
        renew_seconds: float = RENEW_CONNECTION_SECONDS,
        host_token: str | Callable[[], str] | None = None,
        **connection_options: Any,
    ) -> None:
        """``delegate(user, recipient, scope)``: a token that carries the user
        the current call acts for (and the scope of the credential it runs
        under), sent in place of this transport's own token: a
        delegation (``abi:delegated:agent``) acting as this transport's
        identity for a kernel service, or, with ``recipient`` (a call to a
        module host), acting as that module. Only for a transport holding a
        first-party identity (``api``, ``engine``). A transport without one
        calls as itself; one that has one but cannot get a delegation fails
        the call, never calling as itself (which would drop the user).

        ``host_token``: for a transport given a token instead of a key, what a
        call to a module host carries: a token, or a function of the host's
        ``<sa>`` returning the token addressed to that host (a key buys one
        itself). Without one such a transport makes no call to a host: its own
        token must never reach one.

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
        self.delegate = delegate
        # Renewed delegations of a module host's invocations: held token ->
        # (fresh token, its expiry).
        self._renewed: dict[str, tuple[str, float]] = {}
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

    async def access_token(
        self, audience: str = NATS_AUDIENCE, recipient: str | None = None
    ) -> str:
        """The token calls carry: the key's, exchanged as needed, else the
        one this transport was given. ``recipient``: the ``<sa>`` of the module
        host a call is for, which gets a token addressed to it alone."""
        if recipient is not None:
            audience = host_audience(recipient)
        if self.credentials is not None:
            return await self.credentials.access_token(self, audience)
        if recipient is not None:
            source = self.host_token
            if source is None:
                raise NoHostTokenError(
                    "This transport holds no host token: it cannot call a module "
                    "host without handing it a token the kernel services accept"
                )
            return cast(str, source(recipient) if callable(source) else source)
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

    async def delegated_token(
        self, current: Any = None, *, host: str | None = None
    ) -> str | None:
        """The token that carries the user of ``current`` (default: the current
        call), or None when the call has no user or this transport carries
        none (it calls as itself).

        * A module host running an invocation holds the delegation it was
          handed (``CallContext.delegated_token``), used for its kernel calls
          and renewed through its service key when it runs out.
        * A first-party transport asks its ``delegate``; for a call to a module
          host (``host``) the token names that module as the actor."""
        context = current if current is not None else current_call_context()
        served = context.user
        if served is None:
            return None
        if host is None and context.delegated_token:
            return await self._fresh_delegation(context.delegated_token)
        if self.delegate is None:
            return None
        token = self.delegate(served, host, context.scope)
        if inspect.isawaitable(token):
            token = await token
        return cast(str, token)

    async def _fresh_delegation(self, token: str) -> str:
        """``token``, or its renewal when it is about to expire (a run outlives
        the ten minutes of a token); as is when this transport cannot renew."""
        if self.credentials is None or _expiry(token) - time.time() > 60:
            return token
        held = self._renewed.get(token)
        if held is not None and held[1] - time.time() > 60:
            return held[0]
        renewed = await self.credentials.renew_delegation(self, token)
        if len(self._renewed) > 1024:
            self._renewed.clear()
        self._renewed[token] = (renewed, _expiry(renewed))
        return renewed

    async def auth_headers(
        self, current: Any = None, *, host: str | None = None, user: bool = True
    ) -> dict[str, str]:
        """This transport's credentials for a message it sends itself: the
        token that carries the current call's user when it has one to carry
        (``delegated_token``), else its own (a service key's, exchanged as
        needed). ``host``: the ``<sa>`` of the module host that will read the
        message, so the token is addressed to it alone. ``user=False``: as
        itself, whoever the call is for (a module triggering its own job)."""
        token = await self.delegated_token(current, host=host) if user else None
        if token is None:
            token = await self.access_token(recipient=host)
        if not token or "\r" in token or "\n" in token:
            raise ValueError("A nonempty service token without newlines is required")
        return {"Nats-Auth-Token": token}

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
        headers = await self.auth_headers(current, host=host_recipient(subject))
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


def _expiry(token: str) -> float:
    """When ``token`` expires, read without verifying it (the engine verifies
    every token it is sent); 0 for anything unreadable."""
    try:
        payload = token.split(".")[1]
        claims = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
        return float(claims["exp"])
    except (IndexError, ValueError, KeyError, TypeError):
        return 0.0


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
