"""Apps HTTP schemas (``AppInfo``, ``AppsResponse``) returned by the FastAPI
primary adapter. Who may open an app is IAM's (``scopes.py``): a workspace keeps
no state of its own about an app."""

from __future__ import annotations

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
    module_path: str  # e.g. "naas_abi_marketplace.domains.intelligence"
    module_name: str  # human-readable parent module, e.g. "intelligence"
    app_name: str  # folder name under apps/, e.g. "wsr"
    app_id: str  # "<module_path>:<app_name>"
    category: str  # "core" | "ai" | "application" | "domain" | "alpha"

    # Display
    name: str
    description: str = ""
    url: str | None = None
    avatar_url: str | None = None  # image URL for the app icon
    icon_emoji: str | None = None  # emoji fallback when no avatar_url is set

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
    # Optional manifest agent (``module AgentClass``); binds the chat pane when the app is open.
    agent: str | None = None

    # Runtime: a loaded module's app, or one a READY remote module serves.
    installed: bool = False


class AppsResponse(BaseModel):
    apps: list[AppInfo]
