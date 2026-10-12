"""Apps served by remote modules over NATS (abi.app.v1).

docs/adr/20261012_remote-module-apps.md: Nexus lists them next to the apps of
loaded modules and forwards their requests under
``/app-html/remote/<module_id>/<app>/``. The module answers; Nexus is the only
HTTP entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

ROUTE_PREFIX = "/app-html/remote"
# A request body the module accepts (naas_abi_sdk.app_host.MAX_REQUEST_BODY).
MAX_REQUEST_BODY = 1024 * 1024


class RemoteAppUnavailable(Exception):
    """The app could not answer: ``status`` is the HTTP status to return."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status, self.reason = status, reason


@dataclass(frozen=True)
class RemoteApp:
    module_id: str
    name: str
    title: str = ""
    description: str = ""
    category: str = "module"
    icon_emoji: str = ""
    entry: str = "index.html"

    @property
    def root_path(self) -> str:
        return f"{ROUTE_PREFIX}/{self.module_id}/{self.name}"

    @property
    def url(self) -> str:
        return f"{self.root_path}/{self.entry}"

    @property
    def module_path(self) -> str:
        """Its catalog ``module_path``: apart from the paths of loaded modules."""
        return f"remote/{self.module_id}"

    @property
    def app_id(self) -> str:
        """``<module_path>:<app_name>``, as every catalog app."""
        return f"{self.module_path}:{self.name}"


@dataclass(frozen=True)
class AppRequest:
    method: str
    path: str  # below the app's root, starting with "/"
    query: str = ""
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes = b""
    user_id: str = ""


@dataclass(frozen=True)
class AppResponse:
    status: int
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes = b""


class RemoteAppDirectory(Protocol):
    async def list_apps(self) -> list[RemoteApp]:
        """Apps of READY module instances, one entry per module and app."""
        ...

    async def forward(self, module_id: str, app: str, request: AppRequest) -> AppResponse:
        """The module's answer; RemoteAppUnavailable when there is none."""
        ...
