from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.maps.settings.port import MapsSettingsStorePort
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.settings__schema import (
    MapsWorkspaceSettings,
)


class InMemoryMapsSettingsStore(MapsSettingsStorePort):
    """For tests and local runs without Postgres."""

    def __init__(self) -> None:
        self._settings: dict[str, MapsWorkspaceSettings] = {}

    async def get(self, workspace_id: str) -> MapsWorkspaceSettings:
        return self._settings.get(workspace_id, MapsWorkspaceSettings())

    async def save(
        self, workspace_id: str, settings: MapsWorkspaceSettings, *, user_id: str | None
    ) -> None:
        self._settings[workspace_id] = settings
