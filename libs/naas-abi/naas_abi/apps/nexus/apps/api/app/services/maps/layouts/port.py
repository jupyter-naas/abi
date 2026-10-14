"""Secondary port: where a workspace's map layer records are kept.

Hidden flags and layer colors live in the Maps settings document
(``services/maps/settings``), shared with basemaps.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import MapsLayout


class MapsLayoutStorePort(ABC):
    @abstractmethod
    async def list(self, workspace_id: str) -> list[MapsLayout]:
        """Every layer record stored for the workspace."""

    @abstractmethod
    async def save(self, workspace_id: str, layout: MapsLayout, *, user_id: str | None) -> None:
        """Insert or replace the layout with the same id."""

    @abstractmethod
    async def delete(self, workspace_id: str, layout_id: str) -> bool:
        """Remove a layout. Returns False when nothing was stored."""
