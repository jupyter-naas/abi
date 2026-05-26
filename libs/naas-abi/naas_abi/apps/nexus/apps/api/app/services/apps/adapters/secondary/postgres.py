from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.models import AppConfigModel
from naas_abi.apps.nexus.apps.api.app.services.apps.port import (
    AppConfigCreateInput,
    AppConfigRecord,
    AppConfigUpdateInput,
    AppPersistencePort,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class AppSecondaryAdapterPostgres(AppPersistencePort):
    def __init__(
        self,
        db: AsyncSession | None = None,
        db_getter: AsyncSessionGetter | None = None,
    ):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("AppSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    @staticmethod
    def _to_record(model: AppConfigModel) -> AppConfigRecord:
        return AppConfigRecord(
            id=str(model.id),
            workspace_id=str(model.workspace_id),
            app_id=str(model.app_id),
            enabled=bool(model.enabled),
            created_at=datetime.fromisoformat(str(model.created_at)),
            updated_at=datetime.fromisoformat(str(model.updated_at)),
        )

    async def list_by_workspace(self, workspace_id: str) -> list[AppConfigRecord]:
        result = await self.db.execute(
            select(AppConfigModel).where(AppConfigModel.workspace_id == workspace_id)
        )
        return [self._to_record(row) for row in result.scalars().all()]

    async def get(self, workspace_id: str, app_id: str) -> AppConfigRecord | None:
        result = await self.db.execute(
            select(AppConfigModel).where(
                (AppConfigModel.workspace_id == workspace_id)
                & (AppConfigModel.app_id == app_id)
            )
        )
        row = result.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def create(self, data: AppConfigCreateInput) -> AppConfigRecord:
        model = AppConfigModel(
            id=str(uuid4()),
            workspace_id=data.workspace_id,
            app_id=data.app_id,
            enabled=data.enabled,
        )
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return self._to_record(model)

    async def update(
        self, workspace_id: str, app_id: str, updates: AppConfigUpdateInput
    ) -> AppConfigRecord | None:
        result = await self.db.execute(
            select(AppConfigModel).where(
                (AppConfigModel.workspace_id == workspace_id)
                & (AppConfigModel.app_id == app_id)
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        if updates.enabled is not None:
            model.enabled = bool(updates.enabled)
        await self.db.commit()
        await self.db.refresh(model)
        return self._to_record(model)

    async def delete(self, workspace_id: str, app_id: str) -> bool:
        result = await self.db.execute(
            select(AppConfigModel).where(
                (AppConfigModel.workspace_id == workspace_id)
                & (AppConfigModel.app_id == app_id)
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self.db.delete(model)
        await self.db.commit()
        return True
