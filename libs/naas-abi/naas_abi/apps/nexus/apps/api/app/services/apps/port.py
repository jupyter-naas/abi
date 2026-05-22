"""Apps service port + HTTP schemas.

This module groups everything the apps service exposes to its adapters:

* Persistence port (``AppPersistencePort``) + records/inputs used by the
  secondary adapter.
* HTTP-bound pydantic schemas (``AppInfo``, ``AppsResponse``,
  ``AppConfigCreate``, ``AppConfigUpdate``) returned/accepted by the
  FastAPI primary adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# HTTP schemas (pydantic) — consumed by the FastAPI primary adapter
# ---------------------------------------------------------------------------


class AppPricing(BaseModel):
    type: str = "free"
    price: float = 0


class AppInfo(BaseModel):
    """A launchable web application discovered from a module's apps/<name>/manifest.json."""

    # Identity
    module_path: str           # e.g. "naas_abi_marketplace.alpha.wsr"
    module_name: str           # human-readable parent module, e.g. "wsr"
    app_name: str              # folder name under apps/, e.g. "dashboard"
    app_id: str                # "<module_path>:<app_name>"
    category: str              # "core" | "ai" | "application" | "domain" | "alpha"

    # Display
    name: str
    description: str = ""
    url: str | None = None
    avatar_url: str | None = None   # image URL for the app icon
    icon_emoji: str | None = None   # emoji fallback when no avatar_url is set

    # Demo credentials (declared in manifest for shared demo accounts)
    demo_login: str | None = None
    demo_password: str | None = None

    # Optional manifest metadata
    version: str | None = None
    author: str | None = None
    license: str | None = None
    keywords: list[str] = []
    tier: str | None = None
    maintainer: str | None = None
    pricing: AppPricing | None = None
    dependencies: dict[str, Any] = {}

    # Runtime
    installed: bool = False
    # Per-workspace enable state. Defaults to True (apps enabled by default).
    enabled: bool = True


class AppsResponse(BaseModel):
    apps: list[AppInfo]


class AppConfigCreate(BaseModel):
    """Body for ``POST /api/apps/{workspace_id}``."""

    app_id: str
    enabled: bool = True


class AppConfigUpdate(BaseModel):
    """Body for ``PATCH /api/apps/{workspace_id}/{app_id:path}``."""

    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Persistence port + records (consumed by secondary adapters)
# ---------------------------------------------------------------------------


@dataclass
class AppConfigRecord:
    """Per-workspace config row for a single app."""

    id: str
    workspace_id: str
    app_id: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class AppConfigCreateInput:
    workspace_id: str
    app_id: str
    enabled: bool = True


@dataclass
class AppConfigUpdateInput:
    enabled: bool | None = None


class AppPersistencePort(ABC):
    @abstractmethod
    async def list_by_workspace(self, workspace_id: str) -> list[AppConfigRecord]:
        """Return every per-workspace app config record."""

    @abstractmethod
    async def get(self, workspace_id: str, app_id: str) -> AppConfigRecord | None:
        """Return the record for a single (workspace, app) pair, or None."""

    @abstractmethod
    async def create(self, data: AppConfigCreateInput) -> AppConfigRecord:
        """Insert a new config row.

        Implementations should raise ``LookupError``-distinct exceptions on
        duplicate (workspace_id, app_id); the service translates these to
        domain errors.
        """

    @abstractmethod
    async def update(
        self, workspace_id: str, app_id: str, updates: AppConfigUpdateInput
    ) -> AppConfigRecord | None:
        """Update an existing config row; returns ``None`` if absent."""

    @abstractmethod
    async def delete(self, workspace_id: str, app_id: str) -> bool:
        """Remove a config row. Returns True if a row was removed."""
