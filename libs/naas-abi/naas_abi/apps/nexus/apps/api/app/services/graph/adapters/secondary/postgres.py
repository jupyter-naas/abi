from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.models import GraphConfigModel
from naas_abi.apps.nexus.apps.api.app.services.graph.port import (
    GraphConfigCreateInput,
    GraphConfigRecord,
    GraphConfigUpdateInput,
    GraphPersistencePort,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class GraphSecondaryAdapterPostgres(GraphPersistencePort):
    def __init__(
        self,
        db: AsyncSession | None = None,
        db_getter: AsyncSessionGetter | None = None,
    ):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("GraphSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    @staticmethod
    def _to_record(model: GraphConfigModel) -> GraphConfigRecord:
        return GraphConfigRecord(
            id=str(model.id),
            workspace_id=str(model.workspace_id),
            graph_uri=str(model.graph_uri),
            name=str(model.name),
            enabled=bool(model.enabled),
            created_at=datetime.fromisoformat(str(model.created_at)),
            updated_at=datetime.fromisoformat(str(model.updated_at)),
        )

    async def list_by_workspace(self, workspace_id: str) -> list[GraphConfigRecord]:
        result = await self.db.execute(
            select(GraphConfigModel).where(GraphConfigModel.workspace_id == workspace_id)
        )
        return [self._to_record(row) for row in result.scalars().all()]

    async def get(self, workspace_id: str, graph_uri: str) -> GraphConfigRecord | None:
        result = await self.db.execute(
            select(GraphConfigModel).where(
                (GraphConfigModel.workspace_id == workspace_id)
                & (GraphConfigModel.graph_uri == graph_uri)
            )
        )
        row = result.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def create(self, data: GraphConfigCreateInput) -> GraphConfigRecord:
        model = GraphConfigModel(
            id=str(uuid4()),
            workspace_id=data.workspace_id,
            graph_uri=data.graph_uri,
            name=data.name,
            enabled=data.enabled,
        )
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return self._to_record(model)

    async def create_many(self, configs: list[GraphConfigCreateInput]) -> list[GraphConfigRecord]:
        if not configs:
            return []

        models: list[GraphConfigModel] = []
        for data in configs:
            model = GraphConfigModel(
                id=str(uuid4()),
                workspace_id=data.workspace_id,
                graph_uri=data.graph_uri,
                name=data.name,
                enabled=data.enabled,
            )
            self.db.add(model)
            models.append(model)

        await self.db.commit()
        for model in models:
            await self.db.refresh(model)

        return [self._to_record(model) for model in models]

    async def update(
        self,
        workspace_id: str,
        graph_uri: str,
        updates: GraphConfigUpdateInput,
    ) -> GraphConfigRecord | None:
        result = await self.db.execute(
            select(GraphConfigModel).where(
                (GraphConfigModel.workspace_id == workspace_id)
                & (GraphConfigModel.graph_uri == graph_uri)
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None

        if updates.name is not None:
            model.name = str(updates.name)
        if updates.enabled is not None:
            model.enabled = bool(updates.enabled)

        await self.db.commit()
        await self.db.refresh(model)
        return self._to_record(model)

    async def delete(self, workspace_id: str, graph_uri: str) -> bool:
        result = await self.db.execute(
            select(GraphConfigModel).where(
                (GraphConfigModel.workspace_id == workspace_id)
                & (GraphConfigModel.graph_uri == graph_uri)
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self.db.delete(model)
        await self.db.commit()
        return True
