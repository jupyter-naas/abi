from __future__ import annotations

import json

from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.models import MapsBasemapModel
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MapsBasemap,
    MapsBasemapPreview,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.port import MapsBasemapStorePort
from sqlalchemy import delete, select


def _basemap(row: MapsBasemapModel) -> MapsBasemap:
    data = json.loads(str(row.definition))
    data["preview_content_type"] = row.preview_content_type
    data["preview_version"] = row.preview_version or 0
    return MapsBasemap.from_dict(data)


class PostgresMapsBasemapStore(MapsBasemapStorePort):
    """One row per (workspace, basemap): JSON definition plus preview bytes."""

    async def list(self, workspace_id: str) -> list[MapsBasemap]:
        columns = (
            MapsBasemapModel.workspace_id,
            MapsBasemapModel.basemap_id,
            MapsBasemapModel.definition,
            MapsBasemapModel.preview_content_type,
            MapsBasemapModel.preview_version,
        )
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(*columns).where(MapsBasemapModel.workspace_id == workspace_id)
            )
            return [_basemap(row) for row in result.all()]  # type: ignore[arg-type]

    async def save(self, workspace_id: str, basemap: MapsBasemap, *, user_id: str | None) -> None:
        async with AsyncSessionLocal() as db:
            row = await db.get(MapsBasemapModel, (workspace_id, basemap.id))
            if row is None:
                db.add(
                    MapsBasemapModel(
                        workspace_id=workspace_id,
                        basemap_id=basemap.id,
                        definition=basemap.to_json(),
                        preview_version=0,
                        updated_by=user_id,
                    )
                )
            else:
                row.definition = basemap.to_json()  # type: ignore[assignment]
                row.updated_by = user_id  # type: ignore[assignment]
            await db.commit()

    async def delete(self, workspace_id: str, basemap_id: str) -> bool:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(MapsBasemapModel).where(
                    (MapsBasemapModel.workspace_id == workspace_id)
                    & (MapsBasemapModel.basemap_id == basemap_id)
                )
            )
            await db.commit()
            return bool(getattr(result, "rowcount", 0))

    async def get_preview(self, workspace_id: str, basemap_id: str) -> MapsBasemapPreview | None:
        async with AsyncSessionLocal() as db:
            row = await db.get(MapsBasemapModel, (workspace_id, basemap_id))
            if row is None or row.preview is None or not row.preview_content_type:
                return None
            return MapsBasemapPreview(
                content_type=str(row.preview_content_type), content=bytes(row.preview)
            )

    async def set_preview(
        self,
        workspace_id: str,
        basemap_id: str,
        preview: MapsBasemapPreview,
        *,
        user_id: str | None,
    ) -> int:
        async with AsyncSessionLocal() as db:
            row = await db.get(MapsBasemapModel, (workspace_id, basemap_id))
            if row is None:
                raise LookupError(basemap_id)
            version = int(row.preview_version or 0) + 1
            row.preview = preview.content  # type: ignore[assignment]
            row.preview_content_type = preview.content_type  # type: ignore[assignment]
            row.preview_version = version  # type: ignore[assignment]
            row.updated_by = user_id  # type: ignore[assignment]
            await db.commit()
            return version
