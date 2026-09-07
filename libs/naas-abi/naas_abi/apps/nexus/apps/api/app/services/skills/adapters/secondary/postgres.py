from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.models import SkillModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.skills.port import (
    SkillCreateInput,
    SkillPersistencePort,
    SkillRecord,
    SkillUpdateInput,
)
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class SkillSecondaryAdapterPostgres(SkillPersistencePort):
    def __init__(self, db: AsyncSession | None = None, db_getter: AsyncSessionGetter | None = None):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("SkillSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    @staticmethod
    def _to_record(model: SkillModel) -> SkillRecord:
        return SkillRecord(
            id=str(model.id),
            workspace_id=str(model.workspace_id),
            organization_id=str(model.organization_id) if model.organization_id else None,
            user_id=str(model.user_id),
            name=str(model.name),
            slug=str(model.slug),
            description=str(model.description) if model.description else "",
            prompt=str(model.prompt),
            scope=str(model.scope),
            enabled=bool(model.enabled),
            last_used_at=(
                datetime.fromisoformat(str(model.last_used_at)) if model.last_used_at else None
            ),
            created_at=datetime.fromisoformat(str(model.created_at)),
            updated_at=datetime.fromisoformat(str(model.updated_at)),
        )

    @staticmethod
    def _visibility_filter(workspace_id: str, user_id: str):
        # Organization of the target workspace, resolved in-query so callers
        # don't have to pass it around.
        org_id_subq = (
            select(WorkspaceModel.organization_id)
            .where(WorkspaceModel.id == workspace_id)
            .scalar_subquery()
        )
        return or_(
            and_(
                SkillModel.scope == "user",
                SkillModel.user_id == user_id,
                SkillModel.workspace_id == workspace_id,
            ),
            and_(
                SkillModel.scope == "workspace",
                SkillModel.workspace_id == workspace_id,
            ),
            and_(
                SkillModel.scope == "organization",
                SkillModel.organization_id.is_not(None),
                SkillModel.organization_id == org_id_subq,
            ),
        )

    async def list_visible(self, workspace_id: str, user_id: str) -> list[SkillRecord]:
        result = await self.db.execute(
            select(SkillModel)
            .where(self._visibility_filter(workspace_id, user_id))
            .order_by(SkillModel.last_used_at.desc().nulls_last(), SkillModel.updated_at.desc())
        )
        return [self._to_record(row) for row in result.scalars().all()]

    async def get_by_id(self, skill_id: str) -> SkillRecord | None:
        result = await self.db.execute(select(SkillModel).where(SkillModel.id == skill_id))
        skill = result.scalar_one_or_none()
        return self._to_record(skill) if skill else None

    async def get_visible_by_slug(
        self, workspace_id: str, user_id: str, slug: str
    ) -> SkillRecord | None:
        result = await self.db.execute(
            select(SkillModel).where(
                SkillModel.slug == slug,
                self._visibility_filter(workspace_id, user_id),
            )
        )
        skill = result.scalars().first()
        return self._to_record(skill) if skill else None

    async def create(self, data: SkillCreateInput) -> SkillRecord:
        # Denormalize the workspace's organization so organization-scoped
        # skills can be matched across the org with a single column filter.
        org_result = await self.db.execute(
            select(WorkspaceModel.organization_id).where(WorkspaceModel.id == data.workspace_id)
        )
        organization_id = org_result.scalar_one_or_none()

        skill_model = SkillModel(
            id=str(uuid4()),
            workspace_id=data.workspace_id,
            organization_id=organization_id,
            user_id=data.user_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            prompt=data.prompt,
            scope=data.scope,
            enabled=data.enabled,
        )
        self.db.add(skill_model)
        await self.db.commit()
        await self.db.refresh(skill_model)
        return self._to_record(skill_model)

    async def update(self, skill_id: str, updates: SkillUpdateInput) -> SkillRecord | None:
        result = await self.db.execute(select(SkillModel).where(SkillModel.id == skill_id))
        skill_model = result.scalar_one_or_none()
        if skill_model is None:
            return None

        if updates.name is not None:
            skill_model.name = str(updates.name)
        if updates.slug is not None:
            skill_model.slug = str(updates.slug)
        if updates.description is not None:
            skill_model.description = str(updates.description)
        if updates.prompt is not None:
            skill_model.prompt = str(updates.prompt)
        if updates.scope is not None:
            skill_model.scope = str(updates.scope)
        if updates.enabled is not None:
            skill_model.enabled = bool(updates.enabled)

        await self.db.commit()
        await self.db.refresh(skill_model)
        return self._to_record(skill_model)

    async def mark_used(self, skill_id: str, now: datetime) -> SkillRecord | None:
        result = await self.db.execute(select(SkillModel).where(SkillModel.id == skill_id))
        skill_model = result.scalar_one_or_none()
        if skill_model is None:
            return None
        skill_model.last_used_at = now
        await self.db.commit()
        await self.db.refresh(skill_model)
        return self._to_record(skill_model)

    async def delete(self, skill_id: str) -> bool:
        result = await self.db.execute(select(SkillModel).where(SkillModel.id == skill_id))
        skill_model = result.scalar_one_or_none()
        if skill_model is None:
            return False
        await self.db.delete(skill_model)
        await self.db.commit()
        return True
