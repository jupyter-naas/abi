from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.agents.port import (
    AgentCreateInput,
    AgentPersistencePort,
    AgentRecord,
    AgentUpdateInput,
    InferenceServerRecord,
)


class AgentService:
    def __init__(self, adapter: AgentPersistencePort):
        self.adapter = adapter

    async def list_workspace_agents(self, workspace_id: str) -> list[AgentRecord]:
        return await self.adapter.list_by_workspace(workspace_id)

    async def get_agent(self, agent_id: str) -> AgentRecord | None:
        return await self.adapter.get_by_id(agent_id)

    async def get_inference_server(
        self, workspace_id: str, server_id: str
    ) -> InferenceServerRecord | None:
        return await self.adapter.get_inference_server(workspace_id, server_id)

    async def create_agent(self, data: AgentCreateInput) -> AgentRecord:
        return await self.adapter.create(data)

    async def create_agents(self, agents: list[AgentCreateInput]) -> list[AgentRecord]:
        return await self.adapter.create_many(agents)

    async def update_agent(
        self, agent_id: str, updates: AgentUpdateInput
    ) -> AgentRecord | None:
        return await self.adapter.update(agent_id, updates)

    async def delete_agent(self, agent_id: str) -> bool:
        return await self.adapter.delete(agent_id)
