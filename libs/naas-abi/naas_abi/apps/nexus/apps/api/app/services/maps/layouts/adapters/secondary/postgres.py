from __future__ import annotations

import json

from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.models import MapsLayoutModel
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import MapsLayout
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.port import MapsLayoutStorePort
from sqlalchemy import delete, select


class PostgresMapsLayoutStore(MapsLayoutStorePort):
    """One row per (workspace, layout); the definition is a JSON document."""

    async def list(self, workspace_id: str) -> list[MapsLayout]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(MapsLayoutModel).where(MapsLayoutModel.workspace_id == workspace_id)
            )
            return [
                MapsLayout.from_dict(json.loads(str(row.definition)))
                for row in result.scalars().all()
            ]

    async def save(self, workspace_id: str, layout: MapsLayout, *, user_id: str | None) -> None:
        async with AsyncSessionLocal() as db:
            row = await db.get(MapsLayoutModel, (workspace_id, layout.id))
            definition = json.dumps(layout.to_dict())
            if row is None:
                db.add(
                    MapsLayoutModel(
                        workspace_id=workspace_id,
                        layout_id=layout.id,
                        definition=definition,
                        updated_by=user_id,
                    )
                )
            else:
                row.definition = definition  # type: ignore[assignment]
                row.updated_by = user_id  # type: ignore[assignment]
            await db.commit()

    async def delete(self, workspace_id: str, layout_id: str) -> bool:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(MapsLayoutModel).where(
                    (MapsLayoutModel.workspace_id == workspace_id)
                    & (MapsLayoutModel.layout_id == layout_id)
                )
            )
            await db.commit()
            return bool(getattr(result, "rowcount", 0))
