"""Serves a module's web apps on instance-addressed NATS subjects.

Nexus forwards each browser request as an ``abi.app.v1.HttpRequest`` and
returns the ``HttpResponse`` (docs/adr/20261012_remote-module-apps.md). This
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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from naas_abi_proto.app.v1 import app_pb2 as pb
from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb

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


class AppHost:
    def __init__(
        self,
        session: Any,
        apps: dict[str, tuple[AppDescriptor, ASGIApp | None]],
        *,
        max_concurrency: int = DEFAULT_LIMIT,
        idle_seconds: float = IDLE_SECONDS,
    ) -> None:
        self.session, self.apps = session, apps
        self.subscriptions: list[Any] = []
        self.closing = False
        self.idle_seconds = idle_seconds
        self.calls = ConcurrentCalls(max_concurrency)
        # (token, on-behalf-of, app) -> (reuse until, the verified caller's user)
        self._authorized: dict[tuple[str, str, str], tuple[float, Caller]] = {}
        self._etags: dict[Path, tuple[float, int, str]] = {}
        self._lifespans: list[_Lifespan] = []
        # Requests whose app still runs: reading an upload, or streaming its answer.
        self._streams: set[asyncio.Task] = set()

    async def start(self) -> None:
        try:
            for descriptor, asgi in self.apps.values():
                if asgi is not None:
                    lifespan = _Lifespan(asgi, descriptor.name)
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
                        cb=self.calls.callback(
                            partial(self._handle, name), requests=True
                        ),
                    )
                )
            await nc.flush()
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        for subscription in self.subscriptions:
            await subscription.unsubscribe()
        self.subscriptions.clear()
        await self.calls.cancel()
        for task in list(self._streams):
            task.cancel()
        await asyncio.gather(*self._streams, return_exceptions=True)
        for lifespan in reversed(self._lifespans):
            await lifespan.shutdown()
        self._lifespans.clear()

    async def _nc(self) -> Any:
        return await self.session.client.transport.connect()

    def _keep(self, task: asyncio.Task) -> None:
        self._streams.add(task)
        task.add_done_callback(self._streams.discard)

    # -- one request ----------------------------------------------------------

    async def _handle(self, name: str, msg: Any) -> None:
        response = pb.HttpResponse()
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
            answer = await self._answer(name, request)
            response.status = answer.status
            for key, value in answer.headers:
                response.headers.add(name=key, value=value)
            if answer.stream is not None:
                response.body_follows, response.body_inbox = True, answer.stream.inbox
            else:
                response.body = answer.body
        except RPCError as exc:
            response = pb.HttpResponse()
            response.error.code, response.error.message = exc.code, str(exc)
        except Exception:
            logger.exception("App %s failed", name)
            response = pb.HttpResponse()
            response.error.code, response.error.message = "APP_ERROR", "App failed"
        if msg.reply:
            await reply(msg, response.SerializeToString())

    async def _authorize(self, name: str, headers: dict) -> Caller:
        """The verified caller (the actor and the user it acts for, "" for
        none), once discovery allows it to open this app (discovery:OpenApp)."""
        token = headers.get("Nats-Auth-Token", "")
        key = (token, name)
        now = asyncio.get_running_loop().time()
        cached = self._authorized.get(key)
        if cached is not None and now < cached[0]:
            return cached[1]
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
        if len(request.body) > MAX_INLINE_REQUEST_BODY:
            return _text(413, "Request too large")
        if not request.path.startswith("/"):
            raise RPCError("INVALID_ARGUMENT", "App path must start with /")
        if request.body_follows and not request.body_inbox.startswith("_INBOX."):
            raise RPCError("INVALID_ARGUMENT", "A body inbox must be an _INBOX subject")
        descriptor, asgi = self.apps[name]
        method = request.method.upper()
        if method in ("GET", "HEAD") and descriptor.root is not None:
            found = await self._static(descriptor, request)
            if found is not None:
                return found
        if asgi is None:
            return _text(404, "Not found")
        if len(self._streams) >= MAX_STREAMS:
            raise RPCError("MODULE_UNAVAILABLE", "Too many requests in progress")
        return await self._asgi(asgi, request)

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
        if request.method.upper() == "HEAD":
            return _Answer(200, headers)
        if stat.st_size <= INLINE_BYTES:
            return _Answer(200, headers, path.read_bytes())
        if len(self._streams) >= MAX_STREAMS:
            raise RPCError("MODULE_UNAVAILABLE", "Too many responses streaming")
        source = BodySource(await self._nc(), idle_seconds=self.idle_seconds)
        await source.start()
        self._keep(asyncio.create_task(self._send_file(path, source)))
        return _Answer(200, headers, stream=source)

    async def _send_file(self, path: Path, source: BodySource) -> None:
        size = chunk_bytes(getattr(source.nc, "max_payload", 1024 * 1024))
        try:
            with path.open("rb") as file:
                while chunk := await asyncio.to_thread(file.read, size):
                    await source.put(chunk)
            await source.finish()
            await source.gone.wait()  # the last pull, then the linger
        except ReaderGone:
            pass
        finally:
            await source.close()

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

    async def _asgi(self, app: ASGIApp, request: pb.HttpRequest) -> _Answer:
        call = _AsgiCall(self, app, request)
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

    def __init__(self, host: AppHost, app: ASGIApp, request: pb.HttpRequest) -> None:
        self.host, self.app, self.request = host, app, request
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
                self.ready.set_exception(exc)
            elif not self.too_large:
                logger.exception("App failed after it started answering")
                if self.source is not None and not self.source.done.is_set():
                    with contextlib.suppress(ReaderGone):
                        await self.source.fail("APP_ERROR", "App failed")
        finally:
            self.done.set()
            if self.body is not None:
                with contextlib.suppress(Exception):
                    await self.body.aclose()  # stop pulling an unread upload
            if not self.ready.done():
                self.ready.set_result(
                    _text(413, "Request body too large")
                    if self.too_large
                    else _text(500, "App sent no response")
                )
            if self.source is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await self.source.gone.wait()  # the last pull, then the linger
                await self.source.close()
            if self._watcher is not None:
                self._watcher.cancel()

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
            "headers": [
                (h.name.lower().encode("latin-1"), h.value.encode("latin-1"))
                for h in request.headers
                if h.name.lower() not in HOP_BY_HOP
            ],
            "client": None,
            "server": None,
            # Who asked, as discovery verified it: request.scope["abi"]["user_id"]
            # and request.scope["abi"]["principal"].
            "abi": {
                "user_id": request.user_id,
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
                self.body = pull_body(
                    await self.host._nc(),
                    request.body_inbox,
                    max_bytes=max(0, request.max_body_bytes - len(request.body)),
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
                if k.decode("latin-1").lower() not in HOP_BY_HOP
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
            if not more and len(body) <= INLINE_BYTES:
                # The whole response at once, small: inline.
                self.ready.set_result(_Answer(self.status, self.headers, body))
                return
            self.source = BodySource(
                await self.host._nc(), idle_seconds=self.host.idle_seconds
            )
            await self.source.start()
            self._watcher = asyncio.create_task(self._stop_when_reader_gone())
            self.ready.set_result(
                _Answer(self.status, self.headers, stream=self.source)
            )
        size = chunk_bytes(getattr(self.source.nc, "max_payload", 1024 * 1024))
        for start in range(0, len(body), size):
            await self.source.put(body[start : start + size])
        if not more:
            await self.source.finish()


class _Lifespan:
    """Runs an ASGI app's startup and shutdown (FastAPI lifespan and events).

    An app without lifespan support raises on the lifespan scope; it is then
    simply not told about startup or shutdown, as with ``uvicorn --lifespan auto``.
    """

    def __init__(self, app: ASGIApp, name: str) -> None:
        self.app, self.name = app, name
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
                {"type": "lifespan", "asgi": {"version": "3.0", "spec_version": "2.0"}},
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
