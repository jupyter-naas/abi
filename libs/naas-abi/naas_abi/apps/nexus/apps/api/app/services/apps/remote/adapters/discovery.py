"""RemoteAppDirectory over NATS discovery and abi.app.v1 requests.

SDK transports are bound to the event loop that created them, so one client is
kept per running loop (uvicorn's, in the API), as for remote agents. The SDK is
the core ``[nats]`` extra: import it only here, never at module import time.
"""

from __future__ import annotations

import asyncio
import random
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    AppRequest,
    AppResponse,
    RemoteApp,
    RemoteAppUnavailable,
)

CONTRACT_MAJOR = 1
# Discovery is read at most this often: the catalog and every request share it.
SNAPSHOT_SECONDS = 10.0
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
    # (module_id, app) -> READY instance ids serving it
    instances: dict[tuple[str, str], list[str]]


class _Client:
    def __init__(self, discovery: Any, transport: Any, project: str) -> None:
        self.discovery, self.transport, self.project = discovery, transport, project
        self.snapshot: _Snapshot | None = None
        self.lock = asyncio.Lock()


class DiscoveryRemoteAppDirectory:
    def __init__(
        self,
        client_factory: Callable[[], tuple[Any, Any, str]],
        *,
        clock: Callable[[], float] | None = None,
        call_app: Callable[..., Any] | None = None,
    ) -> None:
        """``client_factory`` returns (DiscoveryClient, Transport, project)."""
        self._factory = client_factory
        self._clock = clock
        self._call_app = call_app
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

    async def _snapshot(self, client: _Client, *, fresh: bool = False) -> _Snapshot:
        async with client.lock:
            current = client.snapshot
            if not fresh and current is not None and self._now() - current.taken < SNAPSHOT_SECONDS:
                return current
            apps: dict[tuple[str, str], RemoteApp] = {}
            instances: dict[tuple[str, str], list[str]] = {}
            after = ""
            while True:
                page, after = await client.discovery.list_modules(
                    limit=100, after_instance_id=after
                )
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
                            ),
                        )
                        instances.setdefault(key, []).append(instance.instance_id)
                if not after:
                    break
            client.snapshot = _Snapshot(
                self._now(), sorted(apps.values(), key=lambda a: (a.module_id, a.name)), instances
            )
            return client.snapshot

    async def list_apps(self) -> list[RemoteApp]:
        return list((await self._snapshot(self._client())).apps)

    async def forward(self, module_id: str, app: str, request: AppRequest) -> AppResponse:
        from naas_abi_proto.app.v1 import app_pb2 as pb
        from naas_abi_sdk.app_host import call_app
        from naas_abi_sdk.transport import RPCError
        from nats.errors import NoRespondersError

        client = self._client()
        snapshot = await self._snapshot(client)
        candidates = list(snapshot.instances.get((module_id, app), ()))
        if not candidates:
            # Just started? Read discovery again before answering 404.
            snapshot = await self._snapshot(client, fresh=True)
            candidates = list(snapshot.instances.get((module_id, app), ()))
        if not candidates:
            raise RemoteAppUnavailable(404, "App not published by a ready module")
        message = pb.HttpRequest(
            app=app,
            method=request.method,
            path=request.path,
            query=request.query,
            body=request.body,
            root_path=RemoteApp(module_id, app).root_path,
            user_id=request.user_id,
        )
        for name, value in request.headers:
            message.headers.add(name=name, value=value)
        random.shuffle(candidates)
        last = "No ready instance answered"
        for instance_id in candidates[:2]:  # one retry, elsewhere
            try:
                response = await (self._call_app or call_app)(
                    client.transport, client.project, instance_id, message
                )
            except RPCError as exc:
                if exc.code in _RETRY_ELSEWHERE:
                    last = str(exc)
                    client.snapshot = None  # that instance is gone or going
                    continue
                raise RemoteAppUnavailable(_STATUS.get(exc.code, 502), str(exc)) from exc
            except NoRespondersError:  # stopped since the snapshot
                last = "The module instance stopped"
                client.snapshot = None
                continue
            except TimeoutError as exc:
                raise RemoteAppUnavailable(504, "The app did not answer in time") from exc
            return AppResponse(
                response.status or 200,
                tuple((h.name, h.value) for h in response.headers),
                response.body,
            )
        raise RemoteAppUnavailable(503, last)
