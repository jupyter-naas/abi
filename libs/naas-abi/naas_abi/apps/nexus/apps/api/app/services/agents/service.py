from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.agents.port import (
    AgentCreateInput,
    AgentPersistencePort,
    AgentRecord,
    AgentUpdateInput,
    InferenceServerRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authorization import (
    ensure_scope,
    ensure_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMService


class AgentService:
    def __init__(self, adapter: AgentPersistencePort, iam_service: IAMService | None = None):
        self.adapter = adapter
        self.iam_service = iam_service

    def _ensure_scope(
        self, context: RequestContext, required_scope: str, denied_message: str
    ) -> None:
        ensure_scope(
            context=context,
            required_scope=required_scope,
            denied_message=denied_message,
            iam_service=self.iam_service,
        )

    async def _ensure_workspace_access(self, context: RequestContext, workspace_id: str) -> None:
        await ensure_workspace_access(
            context=context,
            workspace_id=workspace_id,
            denied_message="Workspace access denied",
            required_scope="workspace.read",
            iam_service=self.iam_service,
            workspace_service=None,
        )

    async def list_workspace_agents(
        self,
        context: RequestContext,
        workspace_id: str,
    ) -> list[AgentRecord]:
        self._ensure_scope(context, "agent.read", "Agent access denied")
        await self._ensure_workspace_access(context, workspace_id)
        return await self.adapter.list_by_workspace(workspace_id)

    async def get_agent(self, context: RequestContext, agent_id: str) -> AgentRecord | None:
        self._ensure_scope(context, "agent.read", "Agent access denied")
        agent = await self.adapter.get_by_id(agent_id)
        if agent:
            await self._ensure_workspace_access(context, agent.workspace_id)
        return agent

    async def get_inference_server(
        self,
        context: RequestContext,
        workspace_id: str,
        server_id: str,
    ) -> InferenceServerRecord | None:
        self._ensure_scope(context, "agent.read", "Agent access denied")
        await self._ensure_workspace_access(context, workspace_id)
        return await self.adapter.get_inference_server(workspace_id, server_id)

    async def create_agent(self, context: RequestContext, data: AgentCreateInput) -> AgentRecord:
        self._ensure_scope(context, "agent.create", "Agent access denied")
        await self._ensure_workspace_access(context, data.workspace_id)
        return await self.adapter.create(data)

    async def create_agents(
        self,
        context: RequestContext,
        agents: list[AgentCreateInput],
    ) -> list[AgentRecord]:
        self._ensure_scope(context, "agent.create", "Agent access denied")
        for agent in agents:
            await self._ensure_workspace_access(context, agent.workspace_id)
        return await self.adapter.create_many(agents)

    async def update_agent(
        self,
        context: RequestContext,
        agent_id: str,
        updates: AgentUpdateInput,
    ) -> AgentRecord | None:
        self._ensure_scope(context, "agent.update", "Agent access denied")
        existing = await self.adapter.get_by_id(agent_id)
        if existing:
            await self._ensure_workspace_access(context, existing.workspace_id)
        return await self.adapter.update(agent_id, updates)

    async def delete_agent(self, context: RequestContext, agent_id: str) -> bool:
        self._ensure_scope(context, "agent.delete", "Agent access denied")
        existing = await self.adapter.get_by_id(agent_id)
        if existing:
            await self._ensure_workspace_access(context, existing.workspace_id)
        return await self.adapter.delete(agent_id)
