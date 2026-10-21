"""RemoteAppDirectory over NATS discovery and abi.app.v1 requests.

SDK transports are bound to the event loop that created them, so one client is
kept per running loop (uvicorn's, in the API), as for remote agents. The SDK is
the core ``[nats]`` extra: import it only here, never at module import time.

Large bodies stream (naas_abi_sdk.app_streams): Nexus holds an upload and the
module pulls it as its app reads it; the module holds a large or endless
response and Nexus pulls it as the browser reads it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import weakref
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    DEFAULT_MAX_UPLOAD_BYTES,
    INTERNAL_MODULES,
    AppRequest,
    AppResponse,
    RemoteApp,
    RemoteAppStreamFailed,
    RemoteAppUnavailable,
)

_log = logging.getLogger(__name__)

CONTRACT_MAJOR = 1
# Discovery is read at most this often: the catalog and every request share it.
SNAPSHOT_SECONDS = 10.0
# A name the snapshot does not know reads discovery again (an app that just
# started), but no more than this often, whatever names requests make up.
MISS_SNAPSHOT_SECONDS = 1.0
# The longest a read of discovery may take. Requests and the catalog wait for
# it under one lock, so it bounds how long a slow discovery holds /api/apps.
REFRESH_SECONDS = 5.0
# After a failed read, callers fail at once for this long instead of each
# waiting for a read of its own.
RETRY_AFTER_SECONDS = 5.0
# An app a fresh read did not list is not looked up again for this long:
# stale tabs polling a removed module must not hold the discovery lock.
MISS_SECONDS = 5.0
MAX_MISSES = 1024
# After the last upload chunk, the module answers within its idle limit.
ANSWER_AFTER_UPLOAD_SECONDS = 65.0
# How long the module has to take the error of an upload the browser dropped.
CUT_NOTICE_SECONDS = 2.0
# Where a module's streamed answer is pulled from: the reply inbox its service account
# may publish to (its own connection prefix starts with this).
_INBOX_PREFIX = "_INBOX."
# The module is gone or going: another READY instance may answer.
# Each is raised before the app ran the request, so even a POST is safe to resend.
_RETRY_ELSEWHERE = {"MODULE_UNAVAILABLE", "LEASE_EXPIRED", "UNAVAILABLE"}
_STATUS = {
    "APP_NOT_FOUND": 404,
    "PAYLOAD_TOO_LARGE": 413,
    "DEADLINE_EXCEEDED": 504,
}


@dataclass
class _Snapshot:
    taken: float
    apps: list[RemoteApp]
    # (module_id, app) -> (service account, instance id) of each READY instance serving
    # it: both name its subject.
    instances: dict[tuple[str, str], list[tuple[str, str]]]


class _Client:
    def __init__(self, discovery: Any, transport: Any, upload_transport: Any, project: str) -> None:
        self.discovery, self.project = discovery, project
        # Ordinary requests; and uploads, whose answer waits for the whole body.
        self.transport, self.upload_transport = transport, upload_transport
        self.snapshot: _Snapshot | None = None
        self.failed_at: float | None = None
        self.lock = asyncio.Lock()
        # (module_id, app) -> when a fresh read did not find it
        self.misses: dict[tuple[str, str], float] = {}


class _Retry(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DiscoveryRemoteAppDirectory:
    def __init__(
        self,
        client_factory: Callable[[], tuple[Any, Any, Any, str]],
        *,
        clock: Callable[[], float] | None = None,
        call_app: Callable[..., Any] | None = None,
        refresh_seconds: float = REFRESH_SECONDS,
    ) -> None:
        """``client_factory`` returns (DiscoveryClient, Transport for requests,
        Transport for uploads, discovery project)."""
        self._factory = client_factory
        self._clock = clock
        self._call_app = call_app
        self._refresh_seconds = refresh_seconds
        self._clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _Client] = (
            weakref.WeakKeyDictionary()
        )

    def _client(self) -> _Client:
        loop = asyncio.get_running_loop()
        if loop not in self._clients:
            self._clients[loop] = _Client(*self._factory())
        return self._clients[loop]

    def _now(self) -> float:
        return self._clock() if self._clock else asyncio.get_running_loop().time()

    async def _snapshot(self, client: _Client, *, max_age: float = SNAPSHOT_SECONDS) -> _Snapshot:
        """The apps of READY instances, read at most every ``max_age`` seconds.

        One read at a time, bounded by ``refresh_seconds``; callers that waited
        for it share its result. A failed read fails the callers of the next
        RETRY_AFTER_SECONDS at once (503), rather than each waiting in turn.
        """
        async with client.lock:
            current = client.snapshot
            now = self._now()
            if current is not None and now - current.taken < max_age:
                return current
            if client.failed_at is not None and now - client.failed_at < RETRY_AFTER_SECONDS:
                raise RemoteAppUnavailable(503, "Module discovery is unavailable")
            try:
                client.snapshot = await asyncio.wait_for(
                    self._read(client), timeout=self._refresh_seconds
                )
            except Exception as exc:
                client.failed_at = self._now()
                if isinstance(exc, TimeoutError):
                    raise RemoteAppUnavailable(
                        503, "Module discovery did not answer in time"
                    ) from exc
                # The cause stays in the log; the browser gets no internals.
                _log.warning("Reading module discovery failed", exc_info=True)
                raise RemoteAppUnavailable(503, "Module discovery is unavailable") from exc
            client.failed_at = None
            return client.snapshot

    async def _read(self, client: _Client) -> _Snapshot:
        apps: dict[tuple[str, str], RemoteApp] = {}
        instances: dict[tuple[str, str], list[tuple[str, str]]] = {}
        after = ""
        while True:
            page, after = await client.discovery.list_modules(limit=100, after_instance_id=after)
            for instance in page:
                if instance.status != "READY" or instance.contract_major != CONTRACT_MAJOR:
                    continue
                for app in getattr(instance, "apps", ()):
                    if app.contract_major != CONTRACT_MAJOR:
                        continue
                    key = (instance.module_id, app.name)
                    # Replicas declare identical apps (discovery checks it).
                    apps.setdefault(
                        key,
                        RemoteApp(
                            instance.module_id,
                            app.name,
                            app.title,
                            app.description,
                            app.category or "module",
                            app.icon_emoji,
                            app.entry or "index.html",
                            getattr(app, "max_upload_bytes", 0),
                        ),
                    )
                    instances.setdefault(key, []).append(
                        (instance.service_account, instance.instance_id)
                    )
            if not after:
                break
        return _Snapshot(
            self._now(),
            # The platform's own modules are not in the catalog.
            sorted(
                (a for a in apps.values() if a.module_id not in INTERNAL_MODULES),
                key=lambda a: (a.module_id, a.name),
            ),
            instances,
        )

    async def list_apps(self) -> list[RemoteApp]:
        return list((await self._snapshot(self._client())).apps)

    async def upload_limit(self, module_id: str, app: str) -> int:
        if module_id in INTERNAL_MODULES:
            return DEFAULT_MAX_UPLOAD_BYTES
        snapshot = await self._snapshot(self._client())
        found = next(
            (a for a in snapshot.apps if (a.module_id, a.name) == (module_id, app)),
            None,
        )
        return found.upload_limit if found else DEFAULT_MAX_UPLOAD_BYTES

    async def forward(
        self,
        module_id: str,
        app: str,
        request: AppRequest,
        *,
        service_account: str | None = None,
    ) -> AppResponse:
        from naas_abi_proto.app.v1 import app_pb2 as pb
        from naas_abi_sdk.app_streams import BodySource

        if module_id in INTERNAL_MODULES and service_account is None:
            raise RemoteAppUnavailable(404, "App not published by a ready module")
        client = self._client()
        key = (module_id, app)
        snapshot = await self._snapshot(client)
        candidates = self._bound(snapshot, module_id, app, service_account)
        missed = client.misses.get(key)
        if not candidates and (missed is None or self._now() - missed >= MISS_SECONDS):
            # Just started? Read discovery again before answering 404.
            snapshot = await self._snapshot(client, max_age=MISS_SNAPSHOT_SECONDS)
            candidates = self._bound(snapshot, module_id, app, service_account)
            if not candidates:
                if len(client.misses) >= MAX_MISSES:
                    client.misses.clear()
                client.misses[key] = self._now()
        if not candidates:
            raise RemoteAppUnavailable(404, "App not published by a ready module")
        client.misses.pop(key, None)
        message = pb.HttpRequest(
            app=app,
            method=request.method,
            path=request.path,
            query=request.query,
            body=request.body,
            root_path=request.root_path or RemoteApp(module_id, app).root_path,
            user_id=request.user_id,
            workspace_id=request.workspace_id,
        )
        for name, value in request.headers:
            message.headers.add(name=name, value=value)
        source: BodySource | None = None
        pump: asyncio.Task | None = None
        if request.body_stream is not None:
            nc = await client.upload_transport.connect()
            source = BodySource(nc)
            await source.start()
            pump = asyncio.create_task(
                _pump(request.body_stream, source, request.max_body_bytes, nc)
            )
            message.body_follows, message.body_inbox = True, source.inbox
            message.max_body_bytes = request.max_body_bytes
        random.shuffle(candidates)
        last = "No ready instance answered"
        try:
            for instance in candidates[:2]:  # one retry, elsewhere
                try:
                    response = await self._send(client, instance, message, source, pump)
                except _Retry as exc:
                    last = exc.reason
                    client.snapshot = None  # that instance is gone or going
                    if source is not None and source.pulled:
                        break  # the body went there: it cannot be sent again
                    continue
                return await self._answer(client, response)
            raise RemoteAppUnavailable(503, last)
        finally:
            if pump is not None:
                pump.cancel()
                await asyncio.gather(pump, return_exceptions=True)
            if source is not None:
                await source.close()

    @staticmethod
    def _bound(
        snapshot: _Snapshot, module_id: str, app: str, service_account: str | None
    ) -> list[tuple[str, str]]:
        """The ready instances of the app; with ``service_account``, only those
        that run as that account."""
        return [
            instance
            for instance in snapshot.instances.get((module_id, app), ())
            if service_account is None or instance[0] == service_account
        ]

    async def _send(
        self,
        client: _Client,
        instance: tuple[str, str],
        message: Any,
        source: Any,
        pump: asyncio.Task | None = None,
    ) -> Any:
        from naas_abi_sdk.app_host import call_app
        from naas_abi_sdk.transport import RPCError
        from nats.errors import NoRespondersError

        call = self._call_app or call_app
        transport = client.transport if source is None else client.upload_transport
        service_account, instance_id = instance
        sent = call(
            transport, client.project, instance_id, message, service_account=service_account
        )
        try:
            if source is None:
                return await sent
            return await _upload(sent, source, pump)
        except RPCError as exc:
            if exc.code in _RETRY_ELSEWHERE:
                raise _Retry(str(exc)) from exc
            raise RemoteAppUnavailable(_STATUS.get(exc.code, 502), str(exc)) from exc
        except NoRespondersError as exc:  # stopped since the snapshot
            raise _Retry("The module instance stopped") from exc
        except TimeoutError as exc:
            raise RemoteAppUnavailable(504, "The app did not answer in time") from exc

    async def _answer(self, client: _Client, response: Any) -> AppResponse:
        headers = tuple((h.name, h.value) for h in response.headers)
        if not response.body_follows:
            return AppResponse(response.status or 200, headers, response.body)
        if not response.body_inbox.startswith(_INBOX_PREFIX):
            raise RemoteAppUnavailable(502, "The app answered with an invalid body inbox")
        nc = await client.transport.connect()
        return AppResponse(
            response.status or 200,
            headers,
            body_stream=_Pulled(nc, response.body_inbox),
        )


class UploadCut(Exception):
    """The browser's body ended before it was whole (the browser left)."""


async def _pump(stream: AsyncIterator[bytes], source: Any, max_bytes: int, nc: Any) -> None:
    """Feed the browser's body to ``source`` as the module pulls it. A body
    the browser stops sending (it left) ends with an error at once, so the
    module's app stops reading it now, not after its idle limit."""
    from naas_abi_sdk.app_streams import ReaderGone, chunk_bytes, rechunk

    total = 0
    try:
        async for chunk in rechunk(stream, chunk_bytes(nc.max_payload)):
            total += len(chunk)
            if max_bytes and total > max_bytes:
                await source.fail("PAYLOAD_TOO_LARGE", f"Upload exceeds {max_bytes} bytes")
                return
            await source.put(chunk)
        await source.finish()
    except ReaderGone:
        pass
    except Exception as exc:  # the browser's stream broke: ClientDisconnect
        source.abort("CANCELLED", "The upload was cut off")
        raise UploadCut() from exc


async def _upload(call: Any, source: Any, pump: asyncio.Task | None = None) -> Any:
    """The module's answer to a streamed upload. It comes once the app has read
    what it needs; fail when the module stops pulling (it died, or its app
    stalled), when the browser stops sending, or when the module does not
    answer after the whole body."""
    task = asyncio.ensure_future(call)
    loop = asyncio.get_running_loop()
    finished_at: float | None = None
    waits: set[asyncio.Future] = {task} if pump is None else {task, pump}
    try:
        while True:
            await asyncio.wait(waits, timeout=1.0, return_when=asyncio.FIRST_COMPLETED)
            if task.done():
                return task.result()
            if pump is not None and pump in waits and pump.done():
                waits.discard(pump)
                if not pump.cancelled() and pump.exception() is not None:
                    # The slot is free at once. The module's next pull gets the
                    # error (its app sees a disconnect), if it takes it soon.
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(source.settled(), CUT_NOTICE_SECONDS)
                    raise RemoteAppUnavailable(400, "The upload was cut off")
            if source.done.is_set():
                finished_at = finished_at or loop.time()
                if loop.time() - finished_at > ANSWER_AFTER_UPLOAD_SECONDS:
                    raise RemoteAppUnavailable(504, "The app did not answer the upload")
            elif source.gone.is_set():
                raise RemoteAppUnavailable(502, "The module stopped reading the upload")
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


class _Pulled:
    """A module's response body, pulled as it is iterated.

    An error after the response started (its status line is sent) raises
    RemoteAppStreamFailed: the server aborts the connection, so the browser
    sees the body as cut, not as whole. Closing it tells the module, even
    before the first chunk (a browser that left at once)."""

    def __init__(self, nc: Any, inbox: str) -> None:
        from naas_abi_sdk.app_streams import pull_body

        self.nc, self.inbox = nc, inbox
        self.stream = pull_body(nc, inbox)
        self.started = False

    def __aiter__(self) -> _Pulled:
        return self

    async def __anext__(self) -> bytes:
        from naas_abi_sdk.transport import RPCError

        self.started = True
        try:
            return await self.stream.__anext__()
        except RPCError as exc:
            # The server logs the abort, with this cause: logged once.
            raise RemoteAppStreamFailed(f"{exc.code}: {exc}") from exc

    async def aclose(self) -> None:
        from naas_abi_sdk.app_streams import cancel_body

        if self.started:
            await self.stream.aclose()
        else:
            self.started = True
            await cancel_body(self.nc, self.inbox)
