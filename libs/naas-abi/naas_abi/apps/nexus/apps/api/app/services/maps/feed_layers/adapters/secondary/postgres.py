from __future__ import annotations

import json

from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.models import MapsFeedLayerModel
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.feed_layers__schema import (
    MapsFeedLayer,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.port import (
    MapsFeedLayerStorePort,
)
from sqlalchemy import delete, select


class PostgresMapsFeedLayerStore(MapsFeedLayerStorePort):
    """One row per (workspace, layer); the definition is a JSON document."""

    async def list(self, workspace_id: str) -> list[MapsFeedLayer]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(MapsFeedLayerModel).where(MapsFeedLayerModel.workspace_id == workspace_id)
            )
            return [
                MapsFeedLayer.from_dict(json.loads(str(row.definition)))
                for row in result.scalars().all()
            ]

    async def save(self, workspace_id: str, layer: MapsFeedLayer, *, user_id: str | None) -> None:
        definition = json.dumps({**layer.to_dict(), "shared_from": ""})
        async with AsyncSessionLocal() as db:
            row = await db.get(MapsFeedLayerModel, (workspace_id, layer.id))
            if row is None:
                db.add(
                    MapsFeedLayerModel(
                        workspace_id=workspace_id,
                        layer_id=layer.id,
                        feed_id=layer.feed_id,
                        definition=definition,
                        updated_by=user_id,
                    )
                )
            else:
                row.feed_id = layer.feed_id  # type: ignore[assignment]
                row.definition = definition  # type: ignore[assignment]
                row.updated_by = user_id  # type: ignore[assignment]
            await db.commit()

    async def delete(self, workspace_id: str, layer_id: str) -> bool:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(MapsFeedLayerModel).where(
                    (MapsFeedLayerModel.workspace_id == workspace_id)
                    & (MapsFeedLayerModel.layer_id == layer_id)
                )
            )
            await db.commit()
            return bool(getattr(result, "rowcount", 0))
