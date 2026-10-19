"""Apps served by remote modules over NATS (abi.app.v1).

docs/adr/20261012_remote-module-apps.md: Nexus lists them next to the apps of
loaded modules and forwards their requests under
``/app-html/remote/<module_id>/<app>/``. The module answers; Nexus is the only
HTTP entry point.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

ROUTE_PREFIX = "/app-html/remote"
# Bodies up to this travel inline; larger ones stream, pulled by the reader
# (naas_abi_sdk.app_streams.INLINE_BYTES).
INLINE_BYTES = 256 * 1024
# The largest upload Nexus forwards to an app that sets no max_upload_bytes.
DEFAULT_MAX_UPLOAD_BYTES = 1024 * 1024 * 1024
# Uploads streaming at once to one module, per API worker.
MAX_UPLOADS_PER_MODULE = 16
# Modules the platform runs for itself: their apps are not in the catalog and no
# generic route opens them. The built-in identity provider is reached at /idp,
# by the route that knows which service account it runs as
# (services/idp), and its admin app by services only, over NATS.
INTERNAL_MODULES = frozenset({"idp"})


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
    max_upload_bytes: int = 0  # 0: DEFAULT_MAX_UPLOAD_BYTES

    @property
    def upload_limit(self) -> int:
        return self.max_upload_bytes or DEFAULT_MAX_UPLOAD_BYTES

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
    # A large body, read as the module pulls it (after ``body``).
    body_stream: AsyncIterator[bytes] | None = None
    max_body_bytes: int = 0
    # Where the browser sees the app (its grant URL); the app's own root if empty.
    root_path: str = ""


@dataclass(frozen=True)
class AppResponse:
    status: int
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes = b""
    # A large, chunked or endless body (downloads, server-sent events), pulled
    # from the module as it is iterated; closing it tells the module.
    body_stream: AsyncIterator[bytes] | None = None


class RemoteAppDirectory(Protocol):
    async def list_apps(self) -> list[RemoteApp]:
        """Apps of READY module instances, one entry per module and app."""
        ...

    async def forward(
        self,
        module_id: str,
        app: str,
        request: AppRequest,
        *,
        service_account: str | None = None,
    ) -> AppResponse:
        """The module's answer; RemoteAppUnavailable when there is none.

        ``service_account``: only the instance running as that account (its
        subject token) answers. A module in ``INTERNAL_MODULES`` is forwarded
        to only with one."""
        ...

    async def upload_limit(self, module_id: str, app: str) -> int:
        """The largest request body to forward to the app."""
        ...
