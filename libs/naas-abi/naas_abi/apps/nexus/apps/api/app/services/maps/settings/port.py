"""Secondary port: the per-workspace Maps settings document."""

from __future__ import annotations

from abc import ABC, abstractmethod

from naas_abi.apps.nexus.apps.api.app.services.maps.settings.settings__schema import (
    MapsWorkspaceSettings,
)


class MapsSettingsStorePort(ABC):
    @abstractmethod
    async def get(self, workspace_id: str) -> MapsWorkspaceSettings:
        """The workspace's settings; defaults when nothing was stored."""

    @abstractmethod
    async def save(
        self, workspace_id: str, settings: MapsWorkspaceSettings, *, user_id: str | None
    ) -> None:
        """Replace the workspace's settings document."""
