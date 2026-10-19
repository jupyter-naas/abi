"""In-process RemoteAppDirectory: empty when NATS discovery is off, and a test
double that answers through plain async callables."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    DEFAULT_MAX_UPLOAD_BYTES,
    INTERNAL_MODULES,
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
        return sorted(
            (a for a in self.apps if a.module_id not in INTERNAL_MODULES),
            key=lambda a: (a.module_id, a.name),
        )

    async def forward(
        self,
        module_id: str,
        app: str,
        request: AppRequest,
        *,
        service_account: str | None = None,
    ) -> AppResponse:
        if module_id in INTERNAL_MODULES and service_account is None:
            raise RemoteAppUnavailable(404, "App not published")
        handler = next(
            (fn for a, fn in self.apps.items() if (a.module_id, a.name) == (module_id, app)),
            None,
        )
        if handler is None:
            raise RemoteAppUnavailable(404, "App not published")
        return await handler(request)

    async def upload_limit(self, module_id: str, app: str) -> int:
        found = next((a for a in self.apps if (a.module_id, a.name) == (module_id, app)), None)
        return found.upload_limit if found else DEFAULT_MAX_UPLOAD_BYTES
