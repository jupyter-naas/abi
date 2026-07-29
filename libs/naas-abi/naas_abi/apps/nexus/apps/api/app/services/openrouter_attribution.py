"""OpenRouter attribution headers from Nexus settings (product-agnostic).

OpenRouter uses HTTP-Referer / X-Title for app ranking and analytics.
These must come from deployment config (config.yaml -> Nexus settings),
never from a hard-coded product name.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.config import settings


def openrouter_attribution_headers() -> dict[str, str]:
    referer = (settings.frontend_url or "").strip().rstrip("/") or "http://localhost:3000"
    title = (
        (settings.magic_link_email_app_name or "").strip()
        or (settings.app_name or "").strip()
        or "Nexus"
    )
    return {
        "HTTP-Referer": referer,
        "X-Title": title,
    }
