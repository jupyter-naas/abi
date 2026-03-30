from __future__ import annotations

import os

from naas_abi.apps.nexus.apps.api.app.models import SecretModel, WorkspaceMemberModel
from naas_abi.apps.nexus.apps.api.app.services.providers.port import ProviderAvailabilityPort
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
