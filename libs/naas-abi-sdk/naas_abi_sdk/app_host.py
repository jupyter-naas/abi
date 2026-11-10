"""Serves a module's web apps on instance-addressed NATS subjects.

Nexus forwards each browser request as an ``abi.app.v1.HttpRequest`` and
returns the ``HttpResponse``. This
host authorizes the caller through discovery, then answers with a file of the
app's folder or, for any other path, the app's ASGI application, called in
process: no HTTP server, no port.

Bodies stream (naas_abi_sdk.app_streams): a large upload reaches the app's
``receive()`` chunk by chunk as the app reads it, and a large, chunked or
endless response (a download, server-sent events) leaves as the app sends it.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import mimetypes
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from naas_abi_proto.app.v1 import app_pb2 as pb
from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb
from nats.errors import Error as NATSError
from nats.errors import MaxPayloadError

from naas_abi_sdk import overflow
from naas_abi_sdk.agent_host import _token_expiry
from naas_abi_sdk.app_streams import (
    INLINE_BYTES,
    BodySource,
    BodyTooLarge,
    ReaderGone,
    chunk_bytes,
    pull_body,
)
from naas_abi_sdk.apps import AppDescriptor
from naas_abi_sdk.broker_flush import flush_to_broker
from naas_abi_sdk.concurrency import DEFAULT_LIMIT, ConcurrentCalls
from naas_abi_sdk.messages import reply
from naas_abi_sdk.transport import RPCError

logger = logging.getLogger(__name__)

# Largest inline request body accepted; Nexus streams anything above
# app_streams.INLINE_BYTES.
MAX_INLINE_REQUEST_BODY = 1024 * 1024
MAX_REQUEST_BYTES = MAX_INLINE_REQUEST_BODY + 64 * 1024
# An app that neither reads its body nor answers for this long is stopped (504).
IDLE_SECONDS = 60.0
# Responses streaming at once (downloads, server-sent events) in this process.
MAX_STREAMS = 256
# Uploads streaming into this process's apps at once. They go as fast as the
# browser sends, so they have slots of their own and never hold the slots of
# other requests; one more is refused at once (Nexus tries another instance).
MAX_UPLOADS = 16
# When the host closes, a response still streaming ends with an error, which
# its reader has this long to take.
CLOSE_SECONDS = 3.0
# While the host drains, a response stream whose app sent nothing for this long
# ends with an error: an idle stream (server-sent events, a long poll) never
# ends by itself. Server-sent events end at once.
DRAIN_IDLE_SECONDS = 1.0
AUTHORIZATION_SECONDS = 5.0
MAX_AUTHORIZATIONS = 1024
# The browser assets Nexus serves for in-engine apps.
STATIC_SUFFIXES = frozenset(
    {
        ".css", ".gif", ".html", ".ico", ".jpeg", ".jpg", ".js", ".json",
        ".mjs", ".png", ".svg", ".webp", ".woff", ".woff2",
    }
)  # fmt: skip
# Connection-level headers never cross the hop (RFC 9110 section 7.6.1).
HOP_BY_HOP = frozenset(
    {
        "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailer", "transfer-encoding", "upgrade", "content-length",
    }
)  # fmt: skip
# A response's Content-Length crosses: Nexus sends it, so a reader can tell a
# streamed body that ended early from a whole one.
RESPONSE_HOP_BY_HOP = HOP_BY_HOP - {"content-length"}

ASGIApp = Callable[[dict, Callable[[], Awaitable[dict]], Callable[[dict], Awaitable[None]]], Awaitable[None]]  # fmt: skip


def app_subject(project: str, service_account: str, instance_id: str, name: str) -> str:
    return f"abi.mod.{project}.{service_account or '-'}.{instance_id}.app.{name}.http"


async def call_app(
    transport: Any,
    project: str,
    instance_id: str,
    request: pb.HttpRequest,
    *,
    service_account: str,
) -> pb.HttpResponse:
    """Send ``request`` to the app ``request.app`` of one module instance
    (what Nexus does for each browser request); RPCError on an error reply.
    The reply comes once the app starts its response: give ``transport`` a
    timeout above the longest upload (the module stops an idle app itself)."""
    return await transport.call(
        app_subject(project, service_account, instance_id, request.app),
        request,
        pb.HttpResponse,
    )


@dataclass(frozen=True)
class Caller:
    """A request's verified caller, as discovery answered it."""

    user_id: str = ""
    principal_id: str = ""
    principal_kind: str = ""
    principal_name: str = ""


@dataclass
class _Answer:
    status: int
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: bytes = b""
    # The body follows from this source instead (HttpResponse.body_follows).
    stream: BodySource | None = None


def _text(status: int, message: str) -> _Answer:
    return _Answer(status, [("content-type", "text/plain")], message.encode())


def _header(request: pb.HttpRequest, name: str) -> str:
    return next((h.value for h in request.headers if h.name.lower() == name), "")


def _asgi_headers(request: pb.HttpRequest) -> list[tuple[bytes, bytes]]:
    """The request's headers as ASGI wants them: latin-1 bytes, as HTTP has them."""
    try:
        return [
            (h.name.lower().encode("latin-1"), h.value.encode("latin-1"))
            for h in request.headers
            if h.name.lower() not in HOP_BY_HOP
        ]
    except UnicodeEncodeError:
        raise RPCError("INVALID_ARGUMENT", "A header is not latin-1 text") from None


def _is_upload(msg: Any) -> bool:
    """A request whose body follows: it waits on its sender as long as it lasts."""
    if len(msg.data) > MAX_REQUEST_BYTES:
        return False
    try:
        return pb.HttpRequest.FromString(msg.data).body_follows
    except Exception:  # noqa: BLE001 - _handle answers a malformed request
        return False


class _AppFailed(Exception):
    """The app raised before it answered: never retried elsewhere, since it ran."""


async def _drain_subscription(subscription: Any) -> None:
    """Drain, or at least unsubscribe; nats-py raises when the connection is
    closed or draining, or the subscription already gone."""
    try:
        await subscription.drain()
    except NATSError:
        with contextlib.suppress(NATSError):
            await subscription.unsubscribe()


class AppHost:
    def __init__(
        self,
        session: Any,
        apps: dict[str, tuple[AppDescriptor, ASGIApp | None]],
        *,
        max_concurrency: int = DEFAULT_LIMIT,
        max_uploads: int = MAX_UPLOADS,
        idle_seconds: float = IDLE_SECONDS,
    ) -> None:
        self.session, self.apps = session, apps
        self.subscriptions: list[Any] = []
        self.closing = False
        self.idle_seconds = idle_seconds
        self.calls = ConcurrentCalls(max_concurrency)
        self.uploads = ConcurrentCalls(max_uploads)
        # (token, app) -> (reuse until, the verified caller)
        self._authorized: dict[tuple[str, str], tuple[float, Caller]] = {}
        # One discovery call per token and app at a time; the others wait for it.
        self._authorizing: dict[tuple[str, str], asyncio.Future[Caller]] = {}
        self._etags: dict[Path, tuple[float, int, str]] = {}
        self._lifespans: list[_Lifespan] = []
        # What each app's lifespan put in its state (ASGI lifespan "state").
        self._states: dict[str, dict] = {}
        # Requests whose app still runs: reading an upload, or streaming its answer.
        self._streams: set[asyncio.Task] = set()
        # Response bodies not over yet, lingering ones included.
        self._sources: set[BodySource] = set()
        # ASGI calls whose response streams: a drain ends the idle ones.
        self._responding: set[_AsgiCall] = set()

    async def start(self) -> None:
        try:
            for descriptor, asgi in self.apps.values():
                if asgi is not None:
                    lifespan = _Lifespan(asgi, descriptor.name)
                    self._states[descriptor.name] = lifespan.state
                    await lifespan.startup()
                    self._lifespans.append(lifespan)
            nc = await self._nc()
            for name in self.apps:
                self.subscriptions.append(
                    await nc.subscribe(
                        app_subject(
                            self.session.client.project,
                            self.session.service_account,
                            self.session.instance_id,
                            name,
                        ),
                        cb=self._receiver(name),
                    )
                )
            await flush_to_broker(nc)
        except BaseException:
            await self.close()
            raise

    async def drain(self, timeout: float) -> None:
        """Stop taking requests and let those in progress finish, for up to
        ``timeout`` seconds in all.

        A request arriving now finds no responder, and Nexus sends it to
        another instance; one cut off mid-call would wait out its timeout
        (504). A response still streaming may finish, unless it is idle
        (DRAIN_IDLE_SECONDS) or server-sent events: those end with an error,
        and their readers reconnect to another instance. close() cancels
        whatever is still running afterwards. A NATS connection already
        closed or draining does not stop the shutdown.
        """
        self.closing = True
        self._end_idle_streams()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        def remaining() -> float:
            return max(0.0, deadline - loop.time())

        subscriptions, self.subscriptions = self.subscriptions, []
        steps = [
            asyncio.ensure_future(
                asyncio.gather(*(_drain_subscription(s) for s in subscriptions))
            ),
            asyncio.ensure_future(
                asyncio.gather(self.calls.idle(), self.uploads.idle())
            ),
        ]
        try:
            for step in steps:
                await asyncio.wait({step}, timeout=remaining())
        finally:
            for step in steps:
                step.cancel()
            await asyncio.gather(*steps, return_exceptions=True)
        # Answered, but still reading an upload or streaming the response.
        while self._streams and remaining() > 0:
            self._end_idle_streams()
            await asyncio.wait(
                set(self._streams), timeout=min(remaining(), DRAIN_IDLE_SECONDS / 4)
            )

    def _end_idle_streams(self) -> None:
        """End, with an error, the streamed responses a drain need not wait
        for: server-sent events, and those whose app went quiet. A response
        whose body ended is never cut: its app may still run a background
        task (Starlette runs it after the body), which the drain waits for."""
        now = asyncio.get_running_loop().time()
        for call in list(self._responding):
            if call.body_ended or (
                call.source is not None and call.source.done.is_set()
            ):
                self._responding.discard(call)
            elif call.event_stream or (
                not call.sending and now - call.activity >= DRAIN_IDLE_SECONDS
            ):
                self._responding.discard(call)
                if call.source is not None:
                    call.source.abort("MODULE_UNAVAILABLE", "The module is stopping")
                if call.task is not None:
                    call.task.cancel()

    async def close(self) -> None:
        """Stop serving. A response still streaming (a download, server-sent
        events) ends with an error its reader sees, not a clean end, and the
        host waits CLOSE_SECONDS at most for the readers to take it."""
        self.closing = True
        for subscription in self.subscriptions:
            with contextlib.suppress(Exception):
                await subscription.unsubscribe()
        self.subscriptions.clear()
        await self.calls.cancel()
        await self.uploads.cancel()
        for source in list(self._sources):
            source.abort("MODULE_UNAVAILABLE", "The module stopped")
        for task in list(self._streams):
            task.cancel()
        if self._streams:
            await asyncio.wait(set(self._streams), timeout=CLOSE_SECONDS + 1)
        for source in list(self._sources):
            await source.close()
        self._sources.clear()
        for lifespan in reversed(self._lifespans):
            await lifespan.shutdown()
        self._lifespans.clear()

    async def _nc(self) -> Any:
        return await self.session.client.transport.connect()

    async def _fits_inline(
        self, size: int, headers: Iterable[tuple[str, str]] = ()
    ) -> bool:
        """Whether a body of ``size`` bytes is answered inline: up to
        INLINE_BYTES, and fitting one broker message with its headers and
        envelope. Else it streams (a stream's first message holds only the
        headers)."""
        if size > INLINE_BYTES:
            return False
        total = size + sum(len(k) + len(v) + 8 for k, v in headers)
        if total <= chunk_bytes(0):  # the smallest chunk fits any broker
            return True
        nc = await self._nc()
        return total <= chunk_bytes(getattr(nc, "max_payload", 1024 * 1024))

    async def _source(self) -> BodySource:
        """A new response body, closed with the host."""
        self._sources = {s for s in self._sources if not s.gone.is_set()}
        source = BodySource(await self._nc(), idle_seconds=self.idle_seconds)
        await source.start()
        self._sources.add(source)
        return source

    async def _settle(self, source: BodySource) -> None:
        """Wait until the reader took the body's end, or left; the source then
        lingers for a repeated last pull on its own. While the host closes,
        the reader has CLOSE_SECONDS to take it (the error ``close`` put in),
        even when this wait is cancelled; the cancellation then goes on."""
        try:
            await asyncio.wait_for(
                source.settled(), CLOSE_SECONDS if self.closing else None
            )
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            if self.closing:  # close() cancels; its error is still to be served
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(source.settled(), CLOSE_SECONDS)
            await source.close()
            raise
        if self.closing or not source.done.is_set():
            await source.close()

    def _keep(self, task: asyncio.Task) -> None:
        self._streams.add(task)
        task.add_done_callback(self._streams.discard)

    def _receiver(self, name: str) -> Callable[[Any], Awaitable[None]]:
        """The app's subscription callback: uploads run on slots of their own.

        Once the host drains, a request still queued behind busy calls is
        refused at once (MODULE_UNAVAILABLE: the app never ran, so Nexus may
        send it to another instance) rather than waiting for a slot. The
        subscription's drain waits for its queue to empty, so it ends quickly.
        """
        call = self.calls.callback(partial(self._handle, name), requests=True)
        upload = self.uploads.callback(partial(self._handle, name), requests=True)

        async def receive(msg: Any) -> None:
            if self.closing:
                await self._refuse(msg, "MODULE_UNAVAILABLE", "App is draining")
            elif not _is_upload(msg):
                await call(msg)
            elif self.uploads.in_flight >= self.uploads.limit:
                # Waiting for a slot would hold this subscription's other requests.
                await self._refuse(
                    msg, "MODULE_UNAVAILABLE", "Too many uploads in progress"
                )
            else:
                await upload(msg)

        return receive

    async def _refuse(self, msg: Any, code: str, message: str) -> None:
        if not msg.reply:
            return
        response = pb.HttpResponse()
        response.error.code, response.error.message = code, message
        with contextlib.suppress(Exception):
            await reply(msg, response.SerializeToString())

    # -- one request ----------------------------------------------------------

    async def _handle(self, name: str, msg: Any) -> None:
        response = pb.HttpResponse()
        stream: BodySource | None = None
        try:
            if len(msg.data) > MAX_REQUEST_BYTES or overflow.REQUEST_HEADER in (
                msg.headers or {}
            ):
                raise RPCError("PAYLOAD_TOO_LARGE", "Inline app request exceeds 1 MiB")
            request = pb.HttpRequest.FromString(msg.data)
            if self.closing:
                raise RPCError("MODULE_UNAVAILABLE", "App is draining")
            if request.app not in ("", name):
                raise RPCError("INVALID_ARGUMENT", "App request names another app")
            # The user and the actor are the ones discovery verified, never the
            # request's fields.
            caller = await self._authorize(name, msg.headers or {})
            request.user_id = caller.user_id
            request.principal_id = caller.principal_id
            request.principal_kind = caller.principal_kind
            request.principal_name = caller.principal_name
            if not caller.user_id:
                # The container (and the Nexus workspace) a user opened the
                # app from: with no verified user there is none.
                request.workspace_id = ""
                request.context.container = ""
            answer = await self._answer(name, request)
            response.status = answer.status
            for key, value in answer.headers:
                response.headers.add(name=key, value=value)
            if answer.stream is not None:
                stream = answer.stream
                response.body_follows, response.body_inbox = True, stream.inbox
            else:
                response.body = answer.body
        except RPCError as exc:
            # Raised by this host before the app ran (draining, unauthorized, a
            # bad request): Nexus may retry the retryable ones elsewhere.
            response = pb.HttpResponse()
            response.error.code, response.error.message = exc.code, str(exc)
        except _AppFailed as exc:
            logger.error("App %s failed", name, exc_info=exc.__cause__)
            response = pb.HttpResponse()
            response.error.code, response.error.message = "APP_ERROR", "App failed"
        except Exception:
            logger.exception("App %s failed", name)
            response = pb.HttpResponse()
            response.error.code, response.error.message = "APP_ERROR", "App failed"
        if msg.reply:
            await self._reply(name, msg, response, stream)

    async def _reply(
        self, name: str, msg: Any, response: pb.HttpResponse, stream: BodySource | None
    ) -> None:
        """Send the answer; when it cannot go (too large for one message, or the
        send failed), a short error instead, so Nexus is not left waiting."""
        try:
            await reply(msg, response.SerializeToString())
            return
        except MaxPayloadError:
            logger.warning(
                "App %s answered with more headers than a message holds", name
            )
            message = "The app's response headers are too large"
        except Exception:
            logger.warning("Could not send app %s's answer", name, exc_info=True)
            message = "Could not send the app's answer"
        if stream is not None:
            await stream.close()  # its reader never learnt where it is
        failed = pb.HttpResponse()
        failed.error.code, failed.error.message = "APP_ERROR", message
        with contextlib.suppress(Exception):
            await reply(msg, failed.SerializeToString())

    async def _authorize(self, name: str, headers: dict) -> Caller:
        """The verified caller (the actor and the user it acts for, "" for
        none), once discovery allows it to open this app (discovery:OpenApp)."""
        token = headers.get("Nats-Auth-Token", "")
        key = (token, name)
        now = asyncio.get_running_loop().time()
        cached = self._authorized.get(key)
        if cached is not None and now < cached[0]:
            return cached[1]
        # A page loads many files at once with one token: one discovery call.
        pending = self._authorizing.get(key)
        if pending is None:
            pending = asyncio.ensure_future(self._ask_discovery(name, token))
            self._authorizing[key] = pending
            pending.add_done_callback(partial(self._authorized_now, key))
        return await asyncio.shield(pending)

    def _authorized_now(self, key: tuple[str, str], future: asyncio.Future) -> None:
        self._authorizing.pop(key, None)
        if not future.cancelled():
            future.exception()  # retrieved: every waiter may have left

    async def _ask_discovery(self, name: str, token: str) -> Caller:
        key = (token, name)
        now = asyncio.get_running_loop().time()
        response = await self.session.client._call(
            "authorize_app",
            discovery_pb.AuthorizeAppRequest(
                instance_id=self.session.instance_id,
                lease_token=self.session.lease_token,
                app_name=name,
                caller_token=token,
            ),
            discovery_pb.AuthorizeAppResponse,
        )
        caller = Caller(
            user_id=response.caller_user_id,
            principal_id=response.caller_principal_id,
            principal_kind=response.caller_principal_kind,
            principal_name=response.caller_principal_name,
        )
        lifetime = min(AUTHORIZATION_SECONDS, _token_expiry(token) - time.time())
        if lifetime > 0:
            if len(self._authorized) >= MAX_AUTHORIZATIONS:
                self._authorized = {
                    k: v for k, v in self._authorized.items() if v[0] > now
                }
                while len(self._authorized) >= MAX_AUTHORIZATIONS:
                    del self._authorized[next(iter(self._authorized))]
            self._authorized[key] = (now + lifetime, caller)
        return caller

    async def _answer(self, name: str, request: pb.HttpRequest) -> _Answer:
        descriptor, asgi = self.apps[name]
        if len(request.body) > MAX_INLINE_REQUEST_BODY:
            return _text(413, "Request too large")
        if len(request.body) > descriptor.upload_limit:
            return _text(413, "Request body too large")
        if not request.path.startswith("/"):
            raise RPCError("INVALID_ARGUMENT", "App path must start with /")
        if request.body_follows and not request.body_inbox.startswith("_INBOX."):
            raise RPCError("INVALID_ARGUMENT", "A body inbox must be an _INBOX subject")
        method = request.method.upper()
        if method in ("GET", "HEAD") and descriptor.root is not None:
            found = await self._static(descriptor, request)
            if found is not None:
                return found
        if asgi is None:
            return _text(404, "Not found")
        if len(self._streams) >= MAX_STREAMS:
            raise RPCError("MODULE_UNAVAILABLE", "Too many requests in progress")
        return await self._asgi(asgi, request, descriptor)

    # -- static files ---------------------------------------------------------

    async def _static(
        self, descriptor: AppDescriptor, request: pb.HttpRequest
    ) -> _Answer | None:
        """A file of the app's folder, or None when the path names none."""
        root = descriptor.root
        assert root is not None
        relative = request.path.lstrip("/") or descriptor.entry
        parts = relative.split("/")
        if any(part in ("", ".", "..") for part in parts) or "\\" in relative:
            return None
        if "\x00" in relative:  # no file has it; the OS would raise
            return None
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            return None
        if path.suffix.lower() not in STATIC_SUFFIXES or not path.is_file():
            return None
        if path.name == "manifest.json" and path.parent == root.resolve():
            return None  # Nexus reads the descriptor; the manifest is not an asset
        stat = path.stat()
        etag = self._etag(path, stat.st_mtime, stat.st_size)
        headers = [
            (
                "content-type",
                mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            ),
            ("etag", etag),
            # Revalidated on every load: a new version of the module is seen at once.
            ("cache-control", "no-cache"),
        ]
        if _header(request, "if-none-match") == etag:
            return _Answer(304, headers)
        headers.append(("content-length", str(stat.st_size)))
        if request.method.upper() == "HEAD":
            return _Answer(200, headers)
        if await self._fits_inline(stat.st_size, headers):
            return _Answer(200, headers, path.read_bytes())
        if len(self._streams) >= MAX_STREAMS:
            raise RPCError("MODULE_UNAVAILABLE", "Too many responses streaming")
        source = await self._source()
        self._keep(asyncio.create_task(self._send_file(path, source)))
        return _Answer(200, headers, stream=source)

    async def _send_file(self, path: Path, source: BodySource) -> None:
        size = chunk_bytes(getattr(source.nc, "max_payload", 1024 * 1024))
        try:
            with path.open("rb") as file:
                while chunk := await asyncio.to_thread(file.read, size):
                    await source.put(chunk)
            await source.finish()
        except ReaderGone:
            pass
        except Exception:
            logger.exception("Could not send %s", path.name)
            source.abort("APP_ERROR", "Could not read the file")
        finally:
            await self._settle(source)

    def _etag(self, path: Path, mtime: float, size: int) -> str:
        cached = self._etags.get(path)
        if cached is None or cached[:2] != (mtime, size):
            if size <= INLINE_BYTES:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()[:32]
            else:  # not read whole for a tag
                digest = hashlib.sha256(f"{mtime}:{size}".encode()).hexdigest()[:32]
            cached = (mtime, size, f'"{digest}"')
            self._etags[path] = cached
        return cached[2]

    # -- the ASGI app ---------------------------------------------------------

    async def _asgi(
        self,
        app: ASGIApp,
        request: pb.HttpRequest,
        descriptor: AppDescriptor | None = None,
    ) -> _Answer:
        call = _AsgiCall(self, app, request, descriptor)
        call.task = asyncio.create_task(call.run())
        self._keep(call.task)
        try:
            answer = await call.answer()
        except BaseException:
            call.task.cancel()
            raise
        if call.timed_out:
            call.task.cancel()  # idle before answering: stopped
        return answer


class _AsgiCall:
    """One request through an ASGI app: its body pulled as the app reads it,
    its response answered inline or streamed as the app sends it."""

    def __init__(
        self,
        host: AppHost,
        app: ASGIApp,
        request: pb.HttpRequest,
        descriptor: AppDescriptor | None = None,
    ) -> None:
        self.host, self.app, self.request = host, app, request
        self.descriptor = descriptor or AppDescriptor(request.app or "app")
        self.headers_in = _asgi_headers(request)
        loop = asyncio.get_running_loop()
        self.ready: asyncio.Future[_Answer] = loop.create_future()
        self.activity = loop.time()
        self.done = asyncio.Event()
        self.status: int = 500
        self.headers: list[tuple[str, str]] = []
        self.source: BodySource | None = None
        self.too_large = False
        self.body: Any = None  # the pull iterator, when the body follows
        self.first = True
        self.task: asyncio.Task | None = None
        self.timed_out = False
        self._watcher: asyncio.Task | None = None
        # Inside send(): a body chunk waits for its reader, which is no idling.
        self.sending = False
        self.event_stream = False
        # The app sent its last body message: what runs now is its own work.
        self.body_ended = False

    def _touch(self) -> None:
        self.activity = asyncio.get_running_loop().time()

    async def answer(self) -> _Answer:
        """The response's start, once the app sends it (504 when it stays idle)."""
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.wait({self.ready}, timeout=min(1.0, self.host.idle_seconds))
            if self.ready.done():
                return self.ready.result()
            if loop.time() - self.activity > self.host.idle_seconds:
                self.timed_out = True
                self.ready.set_result(_text(504, "App timed out"))
                return self.ready.result()

    async def run(self) -> None:
        try:
            await self.app(self.scope(), self.receive, self.send)
            if self.source is not None and not self.source.done.is_set():
                # The app returned without its last body message.
                await self.source.finish()
        except (ReaderGone, asyncio.CancelledError):
            pass
        except Exception as exc:
            if not self.ready.done():
                # Even an RPCError of the app's own (a service it called) is
                # the app failing, never the host: Nexus must not resend it.
                failed = _AppFailed()
                failed.__cause__ = exc
                self.ready.set_exception(failed)
            elif not self.too_large:
                logger.exception("App failed after it started answering")
                if self.source is not None and not self.source.done.is_set():
                    with contextlib.suppress(ReaderGone):
                        await self.source.fail("APP_ERROR", "App failed")
        finally:
            self.done.set()
            self.host._responding.discard(self)
            if self.body is not None:
                with contextlib.suppress(Exception):
                    await self.body.aclose()  # stop pulling an unread upload
            if not self.ready.done():
                self.ready.set_result(
                    _text(413, "Request body too large")
                    if self.too_large
                    else _text(500, "App sent no response")
                )
            if self._watcher is not None:
                self._watcher.cancel()
            if self.source is not None:
                await self.host._settle(self.source)

    async def _stop_when_reader_gone(self) -> None:
        """An app awaiting its next event (server-sent events) never learns from
        ``send`` that the reader left: cancel it then. Not after its response
        ended normally, so Starlette background tasks still finish."""
        assert self.source is not None
        await self.source.gone.wait()
        if not self.source.done.is_set() and self.task is not None:
            self.task.cancel()

    def scope(self) -> dict:
        request = self.request
        root_path = request.root_path.rstrip("/")
        path = root_path + request.path
        return {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": request.method.upper(),
            "scheme": _header(request, "x-forwarded-proto") or "https",
            "path": path,
            "raw_path": path.encode(),
            "root_path": root_path,
            "query_string": request.query.encode(),
            "headers": self.headers_in,
            "client": None,
            "server": None,
            # A shallow copy of what the app's lifespan stored, as servers pass it.
            "state": dict(self.host._states.get(self.descriptor.name, {})),
            # Who asked, as discovery verified it: request.scope["abi"]["user_id"]
            # and request.scope["abi"]["principal"]; the container the user
            # opened the app from, the container its calls are made in (its
            # name, empty without a verified user), and the Nexus workspace id
            # of earlier hosts, kept for the apps that read it.
            "abi": {
                "user_id": request.user_id,
                "container": request.context.container,
                "workspace_id": request.workspace_id,
                # The actor, as discovery verified it: who holds the credential,
                # which a service may have used to act for the user above.
                "principal": {
                    "id": request.principal_id,
                    "kind": request.principal_kind,
                    "name": request.principal_name,
                },
            },
        }

    async def receive(self) -> dict:
        request = self.request
        if self.first:
            self.first = False
            if request.body_follows:
                # The app's own limit, whatever the request asks; lower if it asks.
                limit = self.descriptor.upload_limit
                if request.max_body_bytes:
                    limit = min(limit, request.max_body_bytes)
                self.body = pull_body(
                    await self.host._nc(),
                    request.body_inbox,
                    max_bytes=max(0, limit - len(request.body)),
                )
            return {
                "type": "http.request",
                "body": request.body,
                "more_body": request.body_follows,
            }
        if self.body is not None:
            try:
                data = await self.body.__anext__()
                self._touch()
                return {"type": "http.request", "body": data, "more_body": True}
            except StopAsyncIteration:
                self.body = None
                return {"type": "http.request", "body": b"", "more_body": False}
            except (BodyTooLarge, RPCError) as exc:
                self.too_large = isinstance(exc, BodyTooLarge) or (
                    isinstance(exc, RPCError) and exc.code == "PAYLOAD_TOO_LARGE"
                )
                logger.info("App request body ended early: %s", exc)
                self.body = None
                return {"type": "http.disconnect"}
        await self.done.wait()
        return {"type": "http.disconnect"}

    async def send(self, message: dict) -> None:
        self._touch()
        kind = message["type"]
        if kind == "http.response.start":
            self.status = int(message["status"])
            self.headers = [
                (k.decode("latin-1"), v.decode("latin-1"))
                for k, v in message.get("headers", [])
                if k.decode("latin-1").lower() not in RESPONSE_HOP_BY_HOP
            ]
            return
        if kind != "http.response.body":
            return
        body = message.get("body", b"")
        more = message.get("more_body", False)
        if self.source is None:
            if self.ready.done():
                return  # answered already (the app was too slow and got a 504)
            if self.too_large:
                # The app saw a disconnect and answers it (often 500): the
                # caller sent too much, which is what it is told.
                self.ready.set_result(_text(413, "Request body too large"))
                return
            if not more and await self.host._fits_inline(len(body), self.headers):
                # The whole response at once, small: inline.
                self.ready.set_result(_Answer(self.status, self.headers, body))
                return
            self.source = await self.host._source()
            self._watcher = asyncio.create_task(self._stop_when_reader_gone())
            self.event_stream = any(
                k.lower() == "content-type"
                and v.split(";")[0].strip().lower() == "text/event-stream"
                for k, v in self.headers
            )
            self.host._responding.add(self)
            self.ready.set_result(
                _Answer(self.status, self.headers, stream=self.source)
            )
        size = chunk_bytes(getattr(self.source.nc, "max_payload", 1024 * 1024))
        self.sending = True
        try:
            for start in range(0, len(body), size):
                await self.source.put(body[start : start + size])
            if not more:
                await self.source.finish()
                self.body_ended = True
        finally:
            self.sending = False
            self._touch()


class _Lifespan:
    """Runs an ASGI app's startup and shutdown (FastAPI lifespan and events).

    An app without lifespan support raises on the lifespan scope; it is then
    simply not told about startup or shutdown, as with ``uvicorn --lifespan auto``.
    """

    def __init__(self, app: ASGIApp, name: str) -> None:
        self.app, self.name = app, name
        # The lifespan "state": what the app stores at startup, copied into
        # each request's scope (FastAPI lifespans that yield a dict need it).
        self.state: dict = {}
        self.inbox: asyncio.Queue[dict] = asyncio.Queue()
        self.outbox: asyncio.Queue[dict] = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.supported = True

    async def startup(self) -> None:
        self.task = asyncio.create_task(self._run())
        await self.inbox.put({"type": "lifespan.startup"})
        message = await self._next()
        if message["type"] == "lifespan.startup.failed":
            raise RuntimeError(
                f"App {self.name} failed to start: {message.get('message', '')}"
            )

    async def shutdown(self) -> None:
        if self.task is None or not self.supported or self.task.done():
            return
        await self.inbox.put({"type": "lifespan.shutdown"})
        try:
            await asyncio.wait_for(self._next(), 30)
        except asyncio.TimeoutError:  # TimeoutError from 3.11
            logger.warning("App %s did not shut down in time", self.name)
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)

    async def _run(self) -> None:
        try:
            await self.app(
                {
                    "type": "lifespan",
                    "asgi": {"version": "3.0", "spec_version": "2.0"},
                    "state": self.state,
                },
                self.inbox.get,
                self.outbox.put,
            )
        except Exception:  # noqa: BLE001 - no lifespan support
            self.supported = False
        finally:
            await self.outbox.put({"type": "lifespan.unsupported"})

    async def _next(self) -> dict:
        message = await self.outbox.get()
        if message["type"] == "lifespan.unsupported":
            self.supported = False
            return {"type": "lifespan.startup.complete"}
        return message
