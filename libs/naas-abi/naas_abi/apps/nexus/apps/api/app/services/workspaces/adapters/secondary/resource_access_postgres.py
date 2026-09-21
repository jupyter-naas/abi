"""Atomic assignment snapshots; reseeding never overwrites an existing row."""

from __future__ import annotations

import json

from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    WorkspaceModel,
    WorkspaceResourcePolicyModel,
    _utcnow,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.resource_access import (
    PolicyConflictError,
    ResourceAccessService,
    ResourceKind,
    ResourcePolicy,
)
from naas_abi.apps.nexus.graph_policy_config import WorkspaceGraphPolicyConfig
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession


class ResourcePolicyPostgres:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_seed(
        self, workspace_id: str, kind: ResourceKind, seed: dict
    ) -> ResourcePolicy:
        query = (
            select(WorkspaceResourcePolicyModel)
            .where(
                WorkspaceResourcePolicyModel.workspace_id == workspace_id,
                WorkspaceResourcePolicyModel.resource_kind == kind,
            )
            .execution_options(populate_existing=True)
        )
        row = (await self.db.execute(query)).scalar_one_or_none()
        if row is None:
            insert = (
                sqlite_insert
                if self.db.get_bind().dialect.name == "sqlite"
                else pg_insert
            )
            await self.db.execute(
                insert(WorkspaceResourcePolicyModel)
                .values(
                    workspace_id=workspace_id,
                    resource_kind=kind,
                    policy=json.dumps(seed),
                    revision=1,
                    updated_at=_utcnow(),
                )
                .on_conflict_do_nothing(
                    index_elements=["workspace_id", "resource_kind"]
                )
            )
            await self.db.commit()
            row = (await self.db.execute(query)).scalar_one()
        return ResourcePolicy(json.loads(row.policy), row.revision, row.updated_by)

    async def save(
        self,
        workspace_id: str,
        kind: ResourceKind,
        data: dict,
        revision: int,
        user_id: str,
    ) -> ResourcePolicy:
        result = await self.db.execute(
            update(WorkspaceResourcePolicyModel)
            .where(
                WorkspaceResourcePolicyModel.workspace_id == workspace_id,
                WorkspaceResourcePolicyModel.resource_kind == kind,
                WorkspaceResourcePolicyModel.revision == revision,
            )
            .values(
                policy=json.dumps(data),
                revision=revision + 1,
                updated_by=user_id,
                updated_at=_utcnow(),
            )
        )
        if result.rowcount != 1:
            await self.db.rollback()
            raise PolicyConflictError(
                "Assignments changed. Reload before saving again."
            )
        await self.db.commit()
        return ResourcePolicy(data, revision + 1, user_id)


async def load_resource_policy(
    db: AsyncSession, workspace_id: str, kind: ResourceKind
) -> ResourcePolicy:
    # Resolve persisted state first. Later config changes are not an override.
    row = (
        await db.execute(
            select(WorkspaceResourcePolicyModel).where(
                WorkspaceResourcePolicyModel.workspace_id == workspace_id,
                WorkspaceResourcePolicyModel.resource_kind == kind,
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return ResourcePolicy(json.loads(row.policy), row.revision, row.updated_by)
    identity = (
        await db.execute(
            select(WorkspaceModel.slug, OrganizationModel.slug)
            .outerjoin(
                OrganizationModel,
                WorkspaceModel.organization_id == OrganizationModel.id,
            )
            .where(WorkspaceModel.id == workspace_id)
        )
    ).one_or_none()
    if identity is None:
        raise LookupError("Workspace not found")
    matches = [
        ws
        for org in (getattr(live_settings(), "organizations", None) or [])
        if org.slug == identity[1]
        for ws in (getattr(org, "workspaces", None) or [])
        if ws.slug == identity[0]
    ]
    if len(matches) > 1:
        raise ValueError("Ambiguous workspace resource configuration")
    seed = matches[0] if matches else None
    data = (
        getattr(seed, "graphs", WorkspaceGraphPolicyConfig()).model_dump()
        if kind == "graphs"
        else {"enabled": list(getattr(seed, "ontologies", None) or [])}
    )
    return await ResourceAccessService(ResourcePolicyPostgres(db)).load(
        workspace_id, kind, data
    )


async def effective_graph_policies(
    db: AsyncSession,
) -> dict[str, WorkspaceGraphPolicyConfig]:
    """Inventory reflects persisted edits, including workspaces absent from YAML."""
    policies = {
        f"{org.slug}/{ws.slug}": getattr(ws, "graphs", WorkspaceGraphPolicyConfig())
        for org in getattr(live_settings(), "organizations", None) or []
        for ws in getattr(org, "workspaces", None) or []
    }
    rows = await db.execute(
        select(
            WorkspaceResourcePolicyModel.policy,
            WorkspaceModel.slug,
            OrganizationModel.slug,
        )
        .join(
            WorkspaceModel,
            WorkspaceResourcePolicyModel.workspace_id == WorkspaceModel.id,
        )
        .outerjoin(
            OrganizationModel, WorkspaceModel.organization_id == OrganizationModel.id
        )
        .where(WorkspaceResourcePolicyModel.resource_kind == "graphs")
    )
    for data, workspace, organization in rows:
        policies[f"{organization}/{workspace}"] = (
            WorkspaceGraphPolicyConfig.model_validate_json(data)
        )
    return policies
