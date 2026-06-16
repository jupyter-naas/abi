from __future__ import annotations

import json
import os

from naas_abi.apps.nexus.apps.api.app.models import (
    ModelCatalogRecordModel,
    SecretModel,
    WorkspaceMemberModel,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.port import (
    ModelCatalogStorePort,
    ProviderAvailabilityPort,
    StoredModel,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ProvidersSecondaryAdapterPostgres(ProviderAvailabilityPort):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_workspace_ids_for_user(self, user_id: str) -> list[str]:
        result = await self.db.execute(
            select(WorkspaceMemberModel.workspace_id).where(WorkspaceMemberModel.user_id == user_id)
        )
        return [row[0] for row in result.fetchall()]

    async def list_secret_keys_for_workspaces(self, workspace_ids: list[str]) -> set[str]:
        if not workspace_ids:
            return set()
        result = await self.db.execute(
            select(SecretModel.key).where(SecretModel.workspace_id.in_(workspace_ids))
        )
        return {row[0] for row in result.fetchall()}

    async def list_environment_keys(self, key_names: list[str]) -> set[str]:
        return {key for key in key_names if os.getenv(key)}


class ModelCatalogSecondaryAdapterPostgres(ModelCatalogStorePort):
    """Postgres-backed store for marketplace AI model display properties."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _decode_overridden(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        return [str(f) for f in parsed] if isinstance(parsed, list) else []

    @classmethod
    def _to_record(cls, row: ModelCatalogRecordModel) -> StoredModel:
        return StoredModel(
            canonical_id=str(row.canonical_id),
            model_id=str(row.model_id),
            provider=str(row.provider),
            provider_id=str(row.provider_id),
            module_path=str(row.module_path),
            name=row.name,
            description=row.description,
            image=row.image,
            context_window=row.context_window,
            source_name=row.source_name,
            source_description=row.source_description,
            source_image=row.source_image,
            source_context_window=row.source_context_window,
            overridden_fields=cls._decode_overridden(row.overridden_fields),
        )

    async def list_all(self) -> list[StoredModel]:
        result = await self.db.execute(select(ModelCatalogRecordModel))
        return [self._to_record(row) for row in result.scalars().all()]

    async def get(self, canonical_id: str) -> StoredModel | None:
        result = await self.db.execute(
            select(ModelCatalogRecordModel).where(
                ModelCatalogRecordModel.canonical_id == canonical_id
            )
        )
        row = result.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def upsert(self, record: StoredModel) -> StoredModel:
        result = await self.db.execute(
            select(ModelCatalogRecordModel).where(
                ModelCatalogRecordModel.canonical_id == record.canonical_id
            )
        )
        row = result.scalar_one_or_none()
        overridden_json = json.dumps(sorted(set(record.overridden_fields)))

        if row is None:
            row = ModelCatalogRecordModel(canonical_id=record.canonical_id)
            self.db.add(row)

        row.model_id = record.model_id
        row.provider = record.provider
        row.provider_id = record.provider_id
        row.module_path = record.module_path
        row.name = record.name
        row.description = record.description
        row.image = record.image
        row.context_window = record.context_window
        row.source_name = record.source_name
        row.source_description = record.source_description
        row.source_image = record.source_image
        row.source_context_window = record.source_context_window
        row.overridden_fields = overridden_json

        await self.db.commit()
        await self.db.refresh(row)
        return self._to_record(row)
