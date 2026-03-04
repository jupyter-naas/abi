from __future__ import annotations

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


class AgentSecondaryAdapterPostgres(AgentPersistencePort):
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _to_record(model: AgentConfigModel) -> AgentRecord:
        return AgentRecord(
            id=model.id,
            workspace_id=model.workspace_id,
            name=model.name,
            class_name=model.class_name,
            description=model.description,
            system_prompt=model.system_prompt,
            model_id=model.model_id,
            provider=model.provider,
            logo_url=model.logo_url,
            enabled=bool(model.enabled),
            created_at=model.created_at,
            updated_at=model.updated_at,
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
            id=server.id,
            workspace_id=server.workspace_id,
            name=server.name,
            type=server.type,
            endpoint=server.endpoint,
            api_key=server.api_key,
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
            agent_model.name = updates.name
        if updates.class_name is not None:
            agent_model.class_name = updates.class_name
        if updates.description is not None:
            agent_model.description = updates.description
        if updates.system_prompt is not None:
            agent_model.system_prompt = updates.system_prompt
        if updates.model_id is not None:
            agent_model.model_id = updates.model_id
        if updates.enabled is not None:
            agent_model.enabled = updates.enabled

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
