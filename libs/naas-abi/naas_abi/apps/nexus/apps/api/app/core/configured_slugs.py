"""The organization and workspace slugs the loaded configuration names.

Seeding (``core/org_seed.py``) makes and updates those rows; nobody else creates an
organization or workspace with one of these slugs, or renames an organization to one.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings


def _slug(value: object) -> str:
    return str(value or "").strip().lower()


def configured_organization_slugs() -> set[str]:
    return {
        _slug(org.slug)
        for org in getattr(live_settings(), "organizations", None) or []
        if _slug(getattr(org, "slug", None))
    }


def configured_workspace_slugs() -> set[str]:
    return {
        _slug(ws.slug)
        for org in getattr(live_settings(), "organizations", None) or []
        for ws in getattr(org, "workspaces", None) or []
        if _slug(getattr(ws, "slug", None))
    }


__all__ = ["configured_organization_slugs", "configured_workspace_slugs"]
