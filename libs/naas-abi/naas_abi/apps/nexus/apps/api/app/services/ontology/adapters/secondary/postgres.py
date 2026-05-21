from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.models import OntologyConfigModel
from naas_abi.apps.nexus.apps.api.app.services.ontology.port import (
    OntologyConfigCreateInput,
    OntologyConfigRecord,
    OntologyConfigUpdateInput,
    OntologyPersistencePort,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class OntologySecondaryAdapterPostgres(OntologyPersistencePort):
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
            raise RuntimeError("OntologySecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    @staticmethod
    def _to_record(model: OntologyConfigModel) -> OntologyConfigRecord:
        return OntologyConfigRecord(
            id=str(model.id),
            workspace_id=str(model.workspace_id),
            path=str(model.path),
            name=str(model.name),
            module_name=str(model.module_name),
            submodule_name=(
                str(model.submodule_name) if model.submodule_name is not None else None
            ),
            enabled=bool(model.enabled),
            created_at=datetime.fromisoformat(str(model.created_at)),
            updated_at=datetime.fromisoformat(str(model.updated_at)),
        )

    async def list_by_workspace(self, workspace_id: str) -> list[OntologyConfigRecord]:
        result = await self.db.execute(
            select(OntologyConfigModel).where(OntologyConfigModel.workspace_id == workspace_id)
        )
        return [self._to_record(row) for row in result.scalars().all()]

    async def get(self, workspace_id: str, path: str) -> OntologyConfigRecord | None:
        result = await self.db.execute(
            select(OntologyConfigModel).where(
                (OntologyConfigModel.workspace_id == workspace_id)
                & (OntologyConfigModel.path == path)
            )
        )
        row = result.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def create(self, data: OntologyConfigCreateInput) -> OntologyConfigRecord:
        model = OntologyConfigModel(
            id=str(uuid4()),
            workspace_id=data.workspace_id,
            path=data.path,
            name=data.name,
            module_name=data.module_name,
            submodule_name=data.submodule_name,
            enabled=data.enabled,
        )
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return self._to_record(model)

    async def create_many(
        self, configs: list[OntologyConfigCreateInput]
    ) -> list[OntologyConfigRecord]:
        if not configs:
            return []

        models: list[OntologyConfigModel] = []
        for data in configs:
            model = OntologyConfigModel(
                id=str(uuid4()),
                workspace_id=data.workspace_id,
                path=data.path,
                name=data.name,
                module_name=data.module_name,
                submodule_name=data.submodule_name,
                enabled=data.enabled,
            )
            self.db.add(model)
            models.append(model)

        await self.db.commit()
        for model in models:
            await self.db.refresh(model)

        return [self._to_record(model) for model in models]

    async def update(
        self,
        workspace_id: str,
        path: str,
        updates: OntologyConfigUpdateInput,
    ) -> OntologyConfigRecord | None:
        result = await self.db.execute(
            select(OntologyConfigModel).where(
                (OntologyConfigModel.workspace_id == workspace_id)
                & (OntologyConfigModel.path == path)
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None

        if updates.name is not None:
            model.name = str(updates.name)
        if updates.module_name is not None:
            model.module_name = str(updates.module_name)
        if updates.submodule_name is not None:
            model.submodule_name = str(updates.submodule_name)
        if updates.enabled is not None:
            model.enabled = bool(updates.enabled)

        await self.db.commit()
        await self.db.refresh(model)
        return self._to_record(model)

    async def delete(self, workspace_id: str, path: str) -> bool:
        result = await self.db.execute(
            select(OntologyConfigModel).where(
                (OntologyConfigModel.workspace_id == workspace_id)
                & (OntologyConfigModel.path == path)
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self.db.delete(model)
        await self.db.commit()
        return True
