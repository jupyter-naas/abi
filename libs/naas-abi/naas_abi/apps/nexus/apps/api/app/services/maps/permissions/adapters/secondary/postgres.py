from __future__ import annotations

import json

from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.models import (
    MapsGrantModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    nexus_resource,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    MapsGrant,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.port import (
    MapsGrantStorePort,
    WorkspaceDirectoryPort,
    WorkspaceRef,
)
from sqlalchemy import delete, select


def _grant(row: MapsGrantModel) -> MapsGrant:
    raw = row.workspace_ids
    ids = None if raw is None else frozenset(str(v) for v in json.loads(str(raw)))
    return MapsGrant(str(row.kind), str(row.item_id), str(row.owner_workspace_id), ids)


class PostgresMapsGrantStore(MapsGrantStorePort):
    """``maps_grants``: one row per item whose availability differs from the default."""

    async def list(self, kind: str) -> list[MapsGrant]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(MapsGrantModel).where(MapsGrantModel.kind == kind))
            return [_grant(row) for row in result.scalars().all()]

    async def save(self, grant: MapsGrant, *, user_id: str | None) -> None:
        ids = None if grant.workspace_ids is None else json.dumps(sorted(grant.workspace_ids))
        async with AsyncSessionLocal() as db:
            row = await db.get(MapsGrantModel, (grant.kind, grant.item_id, grant.owner))
            if row is None:
                db.add(
                    MapsGrantModel(
                        kind=grant.kind,
                        item_id=grant.item_id,
                        owner_workspace_id=grant.owner,
                        workspace_ids=ids,
                        updated_by=user_id,
                    )
                )
            else:
                row.workspace_ids = ids  # type: ignore[assignment]
                row.updated_by = user_id  # type: ignore[assignment]
            await db.commit()

    async def delete(self, kind: str, item_id: str, owner: str) -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(MapsGrantModel).where(
                    (MapsGrantModel.kind == kind)
                    & (MapsGrantModel.item_id == item_id)
                    & (MapsGrantModel.owner_workspace_id == owner)
                )
            )
            await db.commit()


class PostgresWorkspaceDirectory(WorkspaceDirectoryPort):
    async def administered(self, user_id: str, *, superadmin: bool) -> list[WorkspaceRef]:
        """Every workspace for a platform administrator; else the ones IAM lets the
        user administer (``nexus:UpdateWorkspace``: an admin's, an owner's, or an
        org owner's or admin's through the organization-wide role)."""
        async with AsyncSessionLocal() as db:
            rows = (
                await db.execute(
                    select(
                        WorkspaceModel.id, WorkspaceModel.name, WorkspaceModel.organization_id
                    ).order_by(WorkspaceModel.name)
                )
            ).all()
        if not superadmin:
            rows = await authz.filter_allowed(
                "UpdateWorkspace",
                rows,
                user=user_id,
                resource_of=lambda row: nexus_resource(
                    "workspace", container=workspace_container(row.organization_id, str(row.id))
                ),
            )
        return [WorkspaceRef(str(row.id), str(row.name)) for row in rows]
