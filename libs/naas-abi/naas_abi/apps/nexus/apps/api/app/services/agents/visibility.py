"""Which module agents a workspace turned off (``services/visibility``): today's
enabled flag of its roster, ``agent_configs.enabled``. A module agent with no row
in the workspace is not hidden here: the in-process runtime runs only its enabled
roster anyway (``bind_usable_agents``). Agents the workspace built have no module
scope: their own row's flag is checked where they are used."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import scope_resolver
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.visibility.port import VisibilityReaderPort

Rows = Callable[[str], Awaitable[Iterable[Any]]]


class AgentsVisibility(VisibilityReaderPort):
    """``rows``: a workspace's agent rows (``class_name``, ``provider``, ``enabled``);
    a scope is hidden when it has rows and none is enabled."""

    def __init__(
        self,
        rows: Rows,
        resolver: Callable[[], Callable[[Any], ModuleScope | None]] = scope_resolver,
    ) -> None:
        self._rows = rows
        self._resolver = resolver

    async def hidden(self, workspace_id: str, scopes: Sequence[ModuleScope]) -> set[ModuleScope]:
        resolve = self._resolver()
        shown: dict[ModuleScope, bool] = {}
        for row in await self._rows(workspace_id):
            scope = resolve(row)
            if scope is not None:
                shown[scope] = shown.get(scope, False) or bool(row.enabled)
        return {scope for scope in scopes if shown.get(scope) is False}


async def stored_rows(workspace_id: str) -> list[Any]:
    """``agent_configs`` of the workspace that name a class, in a session of its own."""
    from types import SimpleNamespace

    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.models import AgentConfigModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        found = await db.execute(
            select(
                AgentConfigModel.class_name, AgentConfigModel.provider, AgentConfigModel.enabled
            ).where(
                (AgentConfigModel.workspace_id == workspace_id)
                & AgentConfigModel.class_name.is_not(None)
            )
        )
        return [
            SimpleNamespace(class_name=class_name, provider=provider, enabled=bool(enabled))
            for class_name, provider, enabled in found.all()
        ]


def default_reader() -> AgentsVisibility:
    return AgentsVisibility(stored_rows)
