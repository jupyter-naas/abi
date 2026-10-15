from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.models import MapsSettingsModel
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.port import MapsSettingsStorePort
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.settings__schema import (
    MapsWorkspaceSettings,
)


class PostgresMapsSettingsStore(MapsSettingsStorePort):
    """``maps_settings``: one JSON document per workspace."""

    async def get(self, workspace_id: str) -> MapsWorkspaceSettings:
        async with AsyncSessionLocal() as db:
            row = await db.get(MapsSettingsModel, workspace_id)
            return MapsWorkspaceSettings.from_json(None if row is None else str(row.settings))

    async def save(
        self, workspace_id: str, settings: MapsWorkspaceSettings, *, user_id: str | None
    ) -> None:
        async with AsyncSessionLocal() as db:
            row = await db.get(MapsSettingsModel, workspace_id)
            document = settings.to_json()
            if row is None:
                db.add(
                    MapsSettingsModel(
                        workspace_id=workspace_id, settings=document, updated_by=user_id
                    )
                )
            else:
                row.settings = document  # type: ignore[assignment]
                row.updated_by = user_id  # type: ignore[assignment]
            await db.commit()
