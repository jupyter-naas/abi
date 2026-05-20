from typing import Any

from pydantic import BaseModel


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


class AppsResponse(BaseModel):
    apps: list[AppInfo]
