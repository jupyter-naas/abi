"""Nexus's organizations and workspaces, read from its database, for the sets page."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam_admin.port import (
    OrganizationScopes,
    ScopeDirectory,
    ScopeName,
)
from sqlalchemy import text


class SqlScopeDirectory(ScopeDirectory):
    def __init__(self, engine: Callable[[], Any]) -> None:
        self._engine = engine

    async def organizations(self, org_id: str | None = None) -> list[OrganizationScopes]:
        where = " WHERE id = :org" if org_id else ""
        params = {"org": org_id} if org_id else {}
        async with self._engine().connect() as conn:
            orgs = (
                await conn.execute(
                    text(f"SELECT id, name FROM organizations{where} ORDER BY name, id"),
                    params,
                )
            ).all()
            workspaces = (
                await conn.execute(
                    text(
                        "SELECT id, name, organization_id FROM workspaces"
                        + (" WHERE organization_id = :org" if org_id else "")
                        + " ORDER BY name, id"
                    ),
                    params,
                )
            ).all()
        by_org: dict[str, list[ScopeName]] = {}
        for workspace_id, name, organization_id in workspaces:
            if organization_id:
                by_org.setdefault(str(organization_id), []).append(
                    ScopeName(str(workspace_id), name or str(workspace_id))
                )
        return [
            OrganizationScopes(str(oid), name or str(oid), tuple(by_org.get(str(oid), ())))
            for oid, name in orgs
        ]
