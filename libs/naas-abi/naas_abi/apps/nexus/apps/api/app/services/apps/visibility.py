"""Which apps a workspace turned off (``services/visibility``): today's enabled
flag, ``app_configs.enabled``, else the workspace's catalog seed, else off
(``resolve_app_enabled``, what the catalog shows)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence

from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import resolve_app_enabled
from naas_abi.apps.nexus.apps.api.app.services.apps.scopes import app_scope
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.visibility.port import VisibilityReaderPort

States = Callable[[str], Awaitable[Mapping[str, bool]]]
Seeded = Callable[[str], Awaitable[set[str]]]


class AppsVisibility(VisibilityReaderPort):
    """``states``: a workspace's stored ``{app_id: enabled}``; ``seeded``: the
    app ids its catalog seed turns on."""

    def __init__(self, states: States, seeded: Seeded) -> None:
        self._states = states
        self._seeded = seeded

    async def hidden(self, workspace_id: str, scopes: Sequence[ModuleScope]) -> set[ModuleScope]:
        states = await self._states(workspace_id)
        seeded = await self._seeded(workspace_id)
        shown = {
            scope
            for app_id in {*states, *seeded}
            if resolve_app_enabled(app_id, states, seeded)
            and (scope := app_scope(app_id)) is not None
        }
        return {scope for scope in scopes if scope not in shown}


async def stored_states(workspace_id: str) -> dict[str, bool]:
    """``app_configs`` of the workspace, in a session of its own."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.models import AppConfigModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(AppConfigModel.app_id, AppConfigModel.enabled).where(
                AppConfigModel.workspace_id == workspace_id
            )
        )
        return {str(app_id): bool(enabled) for app_id, enabled in rows.all()}


async def seeded_apps(workspace_id: str) -> set[str]:
    """The apps the workspace's catalog seed (or its config) turns on, as the
    catalog reads them."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import effective_seed_apps
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
        apps__primary_adapter__FastAPI as apps_api,
    )

    return effective_seed_apps(
        await apps_api._workspace_slug(workspace_id),
        await apps_api._workspace_catalog_seed(workspace_id),
    )


def default_reader() -> AppsVisibility:
    return AppsVisibility(stored_states, seeded_apps)
