"""Secondary port: where a workspace's map layouts and hidden flags are kept."""

from __future__ import annotations

from abc import ABC, abstractmethod

from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import MapsLayout


class MapsLayoutStorePort(ABC):
    @abstractmethod
    async def list(self, workspace_id: str) -> list[MapsLayout]:
        """Every custom layout stored for the workspace."""

    @abstractmethod
    async def save(self, workspace_id: str, layout: MapsLayout, *, user_id: str | None) -> None:
        """Insert or replace the layout with the same id."""

    @abstractmethod
    async def delete(self, workspace_id: str, layout_id: str) -> bool:
        """Remove a layout. Returns False when nothing was stored."""

    @abstractmethod
    async def get_hidden(self, workspace_id: str) -> set[str]:
        """Layout ids (built-in or custom) hidden in this workspace."""

    @abstractmethod
    async def set_hidden(
        self, workspace_id: str, layout_ids: set[str], *, user_id: str | None
    ) -> None:
        """Replace the set of hidden layouts."""
