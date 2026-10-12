from __future__ import annotations

from dataclasses import replace

from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MapsBasemap,
    MapsBasemapPreview,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.port import MapsBasemapStorePort


class InMemoryMapsBasemapStore(MapsBasemapStorePort):
    """For tests and local runs without Postgres."""

    def __init__(self) -> None:
        self._basemaps: dict[str, dict[str, MapsBasemap]] = {}
        self._previews: dict[tuple[str, str], MapsBasemapPreview] = {}

    async def list(self, workspace_id: str) -> list[MapsBasemap]:
        return list(self._basemaps.get(workspace_id, {}).values())

    async def save(self, workspace_id: str, basemap: MapsBasemap, *, user_id: str | None) -> None:
        stored = self._basemaps.setdefault(workspace_id, {})
        previous = stored.get(basemap.id)
        stored[basemap.id] = replace(
            basemap,
            preview_content_type=previous.preview_content_type if previous else None,
            preview_version=previous.preview_version if previous else 0,
        )

    async def delete(self, workspace_id: str, basemap_id: str) -> bool:
        self._previews.pop((workspace_id, basemap_id), None)
        return self._basemaps.get(workspace_id, {}).pop(basemap_id, None) is not None

    async def get_preview(self, workspace_id: str, basemap_id: str) -> MapsBasemapPreview | None:
        return self._previews.get((workspace_id, basemap_id))

    async def set_preview(
        self,
        workspace_id: str,
        basemap_id: str,
        preview: MapsBasemapPreview,
        *,
        user_id: str | None,
    ) -> int:
        stored = self._basemaps[workspace_id][basemap_id]
        version = stored.preview_version + 1
        self._basemaps[workspace_id][basemap_id] = replace(
            stored, preview_content_type=preview.content_type, preview_version=version
        )
        self._previews[(workspace_id, basemap_id)] = preview
        return version
