"""What the two LinkedIn page searches share: one search result as a page."""

from __future__ import annotations

from typing import Any


def page_of(result: dict[str, Any]) -> dict[str, Any]:
    pagemap = result.get("pagemap", {})
    return {
        "title": result.get("title"),
        "link": result["link"],
        "description": (pagemap.get("metatags") or [{}])[0].get(
            "og:description", result.get("snippet")
        ),
        "cse_image": (pagemap.get("cse_image") or [{}])[0].get("src"),
    }


async def credentials(module: Any) -> dict[str, str]:
    """The search API key and engine id, from the module's secrets."""
    from naas_abi_apps.common.agents import read_secrets

    return await read_secrets(module.engine, module.configuration.secret_names())
