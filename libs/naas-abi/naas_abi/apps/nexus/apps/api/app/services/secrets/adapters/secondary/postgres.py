from __future__ import annotations

from collections.abc import Callable

from naas_abi.apps.nexus.apps.api.app.models import SecretModel
from naas_abi.apps.nexus.apps.api.app.services.secrets.port import (
    SecretRecord,
    SecretsPersistencePort,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class SecretsSecondaryAdapterPostgres(SecretsPersistencePort):
    def __init__(self, db: AsyncSession | None = None, db_getter: AsyncSessionGetter | None = None):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("SecretsSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    @staticmethod
    def _to_record(model: SecretModel) -> SecretRecord:
        return SecretRecord(
            id=model.id,
            workspace_id=model.workspace_id,
            key=model.key,
            encrypted_value=model.encrypted_value,
            description=model.description or "",
            category=model.category,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_by_workspace(self, workspace_id: str) -> list[SecretRecord]:
        result = await self.db.execute(
            select(SecretModel)
            .where(SecretModel.workspace_id == workspace_id)
            .order_by(SecretModel.key)
        )
        return [self._to_record(row) for row in result.scalars().all()]

    async def get_by_workspace_key(self, workspace_id: str, key: str) -> SecretRecord | None:
        result = await self.db.execute(
            select(SecretModel)
            .where(SecretModel.workspace_id == workspace_id)
            .where(SecretModel.key == key)
        )
        row = result.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def get_by_id(self, secret_id: str) -> SecretRecord | None:
        result = await self.db.execute(select(SecretModel).where(SecretModel.id == secret_id))
        row = result.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def create(self, record: SecretRecord) -> SecretRecord:
        row = SecretModel(
            id=record.id,
            workspace_id=record.workspace_id,
            key=record.key,
            encrypted_value=record.encrypted_value,
            description=record.description,
            category=record.category,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        self.db.add(row)
        await self.db.flush()
        return self._to_record(row)

    async def save(self, record: SecretRecord) -> None:
        result = await self.db.execute(select(SecretModel).where(SecretModel.id == record.id))
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.encrypted_value = record.encrypted_value
        row.description = record.description
        row.category = record.category
        row.updated_at = record.updated_at
        await self.db.flush()

    async def delete(self, secret_id: str) -> bool:
        result = await self.db.execute(select(SecretModel).where(SecretModel.id == secret_id))
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self.db.delete(row)
        return True

    async def commit(self) -> None:
        await self.db.commit()
