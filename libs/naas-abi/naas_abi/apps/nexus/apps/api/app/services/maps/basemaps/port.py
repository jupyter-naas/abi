"""Secondary port: where a workspace's basemaps and their preview images are kept.

Hidden flags live in the Maps settings document (``services/maps/settings``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MapsBasemap,
    MapsBasemapPreview,
)


class MapsBasemapStorePort(ABC):
    @abstractmethod
    async def list(self, workspace_id: str) -> list[MapsBasemap]:
        """Every basemap stored for the workspace (preview metadata, no bytes)."""

    @abstractmethod
    async def save(self, workspace_id: str, basemap: MapsBasemap, *, user_id: str | None) -> None:
        """Insert or replace the definition; an existing preview is kept."""

    @abstractmethod
    async def delete(self, workspace_id: str, basemap_id: str) -> bool:
        """Remove a basemap and its preview. Returns False when nothing was stored."""

    @abstractmethod
    async def get_preview(self, workspace_id: str, basemap_id: str) -> MapsBasemapPreview | None:
        """The stored preview image, if any."""

    @abstractmethod
    async def set_preview(
        self,
        workspace_id: str,
        basemap_id: str,
        preview: MapsBasemapPreview,
        *,
        user_id: str | None,
    ) -> int:
        """Replace the preview of a stored basemap. Returns the new preview version."""
