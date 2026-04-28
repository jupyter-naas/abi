from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.models import AgentConfigModel, InferenceServerModel
from naas_abi.apps.nexus.apps.api.app.services.agents.port import (
    AgentCreateInput,
    AgentPersistencePort,
    AgentRecord,
    AgentUpdateInput,
    InferenceServerRecord,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class AgentSecondaryAdapterPostgres(AgentPersistencePort):
    def __init__(self, db: AsyncSession | None = None, db_getter: AsyncSessionGetter | None = None):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("AgentSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    @staticmethod
    def _to_record(model: AgentConfigModel) -> AgentRecord:
        return AgentRecord(
            id=str(model.id),
            workspace_id=str(model.workspace_id),
            name=str(model.name),
            class_name=str(model.class_name),
            description=str(model.description),
            system_prompt=str(model.system_prompt),
            model_id=str(model.model_id),
            provider=str(model.provider),
            logo_url=str(model.logo_url),
            enabled=bool(model.enabled),
            created_at=datetime.fromisoformat(str(model.created_at)),
            updated_at=datetime.fromisoformat(str(model.updated_at)),
        )

    async def list_by_workspace(self, workspace_id: str) -> list[AgentRecord]:
        result = await self.db.execute(
            select(AgentConfigModel).where(AgentConfigModel.workspace_id == workspace_id)
        )
        return [self._to_record(row) for row in result.scalars().all()]

    async def get_by_id(self, agent_id: str) -> AgentRecord | None:
        result = await self.db.execute(
            select(AgentConfigModel).where(AgentConfigModel.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        return self._to_record(agent) if agent else None

    async def get_inference_server(
        self, workspace_id: str, server_id: str
    ) -> InferenceServerRecord | None:
        result = await self.db.execute(
            select(InferenceServerModel).where(
                (InferenceServerModel.id == server_id)
                & (InferenceServerModel.workspace_id == workspace_id)
            )
        )
        server = result.scalar_one_or_none()
        if server is None:
            return None
        return InferenceServerRecord(
            id=str(server.id),
            workspace_id=str(server.workspace_id),
            name=str(server.name),
            type=str(server.type),
            endpoint=str(server.endpoint),
            api_key=str(server.api_key),
        )

    async def create(self, data: AgentCreateInput) -> AgentRecord:
        agent_model = AgentConfigModel(
            id=str(uuid4()),
            workspace_id=data.workspace_id,
            name=data.name,
            class_name=data.class_name,
            description=data.description,
            system_prompt=data.system_prompt,
            model_id=data.model_id,
            provider=data.provider,
            logo_url=data.logo_url,
            enabled=data.enabled,
        )
        self.db.add(agent_model)
        await self.db.commit()
        await self.db.refresh(agent_model)
        return self._to_record(agent_model)

    async def create_many(self, agents: list[AgentCreateInput]) -> list[AgentRecord]:
        if not agents:
            return []

        models: list[AgentConfigModel] = []
        for data in agents:
            model = AgentConfigModel(
                id=str(uuid4()),
                workspace_id=data.workspace_id,
                name=data.name,
                class_name=data.class_name,
                description=data.description,
                system_prompt=data.system_prompt,
                model_id=data.model_id,
                provider=data.provider,
                logo_url=data.logo_url,
                enabled=data.enabled,
            )
            self.db.add(model)
            models.append(model)

        await self.db.commit()
        for model in models:
            await self.db.refresh(model)

        return [self._to_record(model) for model in models]

    async def update(self, agent_id: str, updates: AgentUpdateInput) -> AgentRecord | None:
        result = await self.db.execute(
            select(AgentConfigModel).where(AgentConfigModel.id == agent_id)
        )
        agent_model = result.scalar_one_or_none()
        if agent_model is None:
            return None

        if updates.name is not None:
            agent_model.name = str(updates.name)
        if updates.class_name is not None:
            agent_model.class_name = str(updates.class_name)
        if updates.description is not None:
            agent_model.description = str(updates.description)
        if updates.system_prompt is not None:
            agent_model.system_prompt = str(updates.system_prompt)
        if updates.model_id is not None:
            agent_model.model_id = str(updates.model_id)
        if updates.logo_url is not None:
            agent_model.logo_url = str(updates.logo_url)
        if updates.enabled is not None:
            agent_model.enabled = bool(updates.enabled)

        await self.db.commit()
        await self.db.refresh(agent_model)
        return self._to_record(agent_model)

    async def delete(self, agent_id: str) -> bool:
        result = await self.db.execute(
            select(AgentConfigModel).where(AgentConfigModel.id == agent_id)
        )
        agent_model = result.scalar_one_or_none()
        if agent_model is None:
            return False
        await self.db.delete(agent_model)
        await self.db.commit()
        return True
