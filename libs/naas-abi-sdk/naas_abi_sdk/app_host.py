"""Serves a module's web apps on instance-addressed NATS subjects.

Nexus forwards each browser request as an ``abi.app.v1.HttpRequest`` and
returns the ``HttpResponse`` (docs/adr/20261012_remote-module-apps.md). This
host authorizes the caller through discovery, then answers with a file of the
app's folder or, for any other path, the app's ASGI application, called in
process: no HTTP server, no port.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from naas_abi_proto.app.v1 import app_pb2 as pb
from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb
from nats.errors import MaxPayloadError

from naas_abi_sdk import overflow
from naas_abi_sdk.agent_host import _token_expiry
from naas_abi_sdk.apps import AppDescriptor
from naas_abi_sdk.concurrency import DEFAULT_LIMIT, ConcurrentCalls
from naas_abi_sdk.messages import reply
from naas_abi_sdk.transport import RPCError

logger = logging.getLogger(__name__)

MAX_REQUEST_BODY = 1024 * 1024
# The envelope (headers, path) on top of the body.
MAX_REQUEST_BYTES = MAX_REQUEST_BODY + 64 * 1024
MAX_RESPONSE_BODY = 6 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 60.0
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


def app_subject(project: str, instance_id: str, name: str) -> str:
    return f"abi.mod.{project}.{instance_id}.app.{name}.http"


@dataclass
class _Answer:
    status: int
    headers: list[tuple[str, str]]
    body: bytes = b""


class _TooLarge(Exception):
    pass


def _header(request: pb.HttpRequest, name: str) -> str:
    return next((h.value for h in request.headers if h.name.lower() == name), "")


class AppHost:
    def __init__(
        self,
        session: Any,
        apps: dict[str, tuple[AppDescriptor, ASGIApp | None]],
        *,
        max_concurrency: int = DEFAULT_LIMIT,
    ) -> None:
        self.session, self.apps = session, apps
        self.subscriptions: list[Any] = []
        self.closing = False
        self.calls = ConcurrentCalls(max_concurrency)
        self._authorized: dict[tuple[str, str], tuple[float, str]] = {}
        self._etags: dict[Path, tuple[float, int, str]] = {}
        self._lifespans: list[_Lifespan] = []

    async def start(self) -> None:
        try:
            for descriptor, asgi in self.apps.values():
                if asgi is not None:
                    lifespan = _Lifespan(asgi, descriptor.name)
                    await lifespan.startup()
                    self._lifespans.append(lifespan)
            nc = await self.session.client.transport.connect()
            for name in self.apps:
                self.subscriptions.append(
                    await nc.subscribe(
                        app_subject(
                            self.session.client.project, self.session.instance_id, name
                        ),
                        cb=self.calls.callback(partial(self._handle, name)),
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
        for lifespan in reversed(self._lifespans):
            await lifespan.shutdown()
        self._lifespans.clear()

    # -- one request ----------------------------------------------------------

    async def _handle(self, name: str, msg: Any) -> None:
        response = pb.HttpResponse()
        try:
            if len(msg.data) > MAX_REQUEST_BYTES or overflow.REQUEST_HEADER in (
                msg.headers or {}
            ):
                raise RPCError("PAYLOAD_TOO_LARGE", "App request exceeds 1 MiB")
            request = pb.HttpRequest.FromString(msg.data)
            if self.closing:
                raise RPCError("MODULE_UNAVAILABLE", "App is draining")
            if request.app not in ("", name):
                raise RPCError("INVALID_ARGUMENT", "App request names another app")
            await self._authorize(name, (msg.headers or {}).get("Nats-Auth-Token", ""))
            answer = await self._answer(name, request)
            response.status = answer.status
            for key, value in answer.headers:
                response.headers.add(name=key, value=value)
            response.body = answer.body
        except RPCError as exc:
            response = pb.HttpResponse()
            response.error.code, response.error.message = exc.code, str(exc)
        except Exception:
            logger.exception("App %s failed", name)
            response = pb.HttpResponse()
            response.error.code, response.error.message = "APP_ERROR", "App failed"
        if msg.reply:
            try:
                await reply(msg, response.SerializeToString())
            except MaxPayloadError:
                # Over this broker's max_payload (nats-server's default is 1 MB).
                too_large = pb.HttpResponse()
                too_large.error.code = "PAYLOAD_TOO_LARGE"
                too_large.error.message = (
                    "App response exceeds the broker's max_payload"
                )
                await reply(msg, too_large.SerializeToString())

    async def _authorize(self, name: str, token: str) -> str:
        now = asyncio.get_running_loop().time()
        cached = self._authorized.get((token, name))
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
        lifetime = min(AUTHORIZATION_SECONDS, _token_expiry(token) - time.time())
        if lifetime > 0:
            if len(self._authorized) >= MAX_AUTHORIZATIONS:
                self._authorized = {
                    k: v for k, v in self._authorized.items() if v[0] > now
                }
                while len(self._authorized) >= MAX_AUTHORIZATIONS:
                    del self._authorized[next(iter(self._authorized))]
            self._authorized[(token, name)] = (now + lifetime, response.caller_identity)
        return response.caller_identity

    async def _answer(self, name: str, request: pb.HttpRequest) -> _Answer:
        if len(request.body) > MAX_REQUEST_BODY:
            return _Answer(413, [("content-type", "text/plain")], b"Request too large")
        if not request.path.startswith("/"):
            raise RPCError("INVALID_ARGUMENT", "App path must start with /")
        descriptor, asgi = self.apps[name]
        method = request.method.upper()
        if method in ("GET", "HEAD") and descriptor.root is not None:
            found = self._static(descriptor, request)
            if found is not None:
                return found
        if asgi is None:
            return _Answer(404, [("content-type", "text/plain")], b"Not found")
        try:
            return await asyncio.wait_for(
                _call_asgi(asgi, request), REQUEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:  # TimeoutError from 3.11
            return _Answer(504, [("content-type", "text/plain")], b"App timed out")
        except _TooLarge:
            return _Answer(
                502, [("content-type", "text/plain")], b"App response exceeds 6 MiB"
            )

    # -- static files ---------------------------------------------------------

    def _static(
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
        if stat.st_size > MAX_RESPONSE_BODY:
            return _Answer(502, [("content-type", "text/plain")], b"File exceeds 6 MiB")
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
        body = b"" if request.method.upper() == "HEAD" else path.read_bytes()
        return _Answer(200, headers, body)

    def _etag(self, path: Path, mtime: float, size: int) -> str:
        cached = self._etags.get(path)
        if cached is None or cached[:2] != (mtime, size):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:32]
            cached = (mtime, size, f'"{digest}"')
            self._etags[path] = cached
        return cached[2]


# -- ASGI, in process -------------------------------------------------------------


async def _call_asgi(app: ASGIApp, request: pb.HttpRequest) -> _Answer:
    root_path = request.root_path.rstrip("/")
    path = root_path + request.path
    scope = {
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
        # Who asked, as Nexus vouches for it: request.scope["abi"]["user_id"].
        "abi": {"user_id": request.user_id},
    }
    sent = False
    done = asyncio.Event()

    async def receive() -> dict:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": request.body, "more_body": False}
        await done.wait()
        return {"type": "http.disconnect"}

    status, headers, chunks, size = 500, [], [], 0

    async def send(message: dict) -> None:
        nonlocal status, headers, size
        if message["type"] == "http.response.start":
            status = int(message["status"])
            headers = [
                (k.decode("latin-1"), v.decode("latin-1"))
                for k, v in message.get("headers", [])
                if k.decode("latin-1").lower() not in HOP_BY_HOP
            ]
        elif message["type"] == "http.response.body":
            body = message.get("body", b"")
            size += len(body)
            if size > MAX_RESPONSE_BODY:
                raise _TooLarge()
            chunks.append(body)
            if not message.get("more_body", False):
                done.set()

    try:
        await app(scope, receive, send)
    finally:
        done.set()
    return _Answer(status, headers, b"".join(chunks))


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
