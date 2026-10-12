"""In-process RemoteAppDirectory: empty when NATS discovery is off, and a test
double that answers through plain async callables."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    AppRequest,
    AppResponse,
    RemoteApp,
    RemoteAppUnavailable,
)

Handler = Callable[[AppRequest], Awaitable[AppResponse]]


class InMemoryRemoteAppDirectory:
    def __init__(self, apps: Mapping[RemoteApp, Handler] | None = None) -> None:
        self.apps = dict(apps or {})

    async def list_apps(self) -> list[RemoteApp]:
        return sorted(self.apps, key=lambda a: (a.module_id, a.name))

    async def forward(self, module_id: str, app: str, request: AppRequest) -> AppResponse:
        handler = next(
            (fn for a, fn in self.apps.items() if (a.module_id, a.name) == (module_id, app)),
            None,
        )
        if handler is None:
            raise RemoteAppUnavailable(404, "App not published")
        return await handler(request)
