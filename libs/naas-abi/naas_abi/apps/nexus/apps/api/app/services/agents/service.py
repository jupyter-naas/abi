from __future__ import annotations

import re

from naas_abi.apps.nexus.apps.api.app.services.agents.port import (
    AgentCreateInput,
    AgentPersistencePort,
    AgentRecord,
    AgentUpdateInput,
    InferenceServerRecord,
)

# A model id names one model or one agent on a server, and it is placed in
# provider URLs: a name, never a path or a query.
_MODEL_ID = re.compile(r"[A-Za-z0-9@][A-Za-z0-9._:@+/-]{0,199}")


def model_id_refusal(value: str | None) -> str | None:
    """Why ``value`` cannot be an agent's ``model_id``, or None when it can."""
    if value is None or value == "":
        return None
    if not _MODEL_ID.fullmatch(value) or any(part in {"", ".", ".."} for part in value.split("/")):
        return (
            "model_id must be a model name: letters, digits and . _ : @ + / -, "
            "with no empty, '.' or '..' part between slashes"
        )
    return None


class AgentService:
    """Agent configurations of a workspace.

    Who may do what is decided by IAM at the route (``ListAgents``,
    ``UpdateAgent``...), before this service is reached; it only persists.
    """

    def __init__(self, adapter: AgentPersistencePort):
        self.adapter = adapter

    async def list_workspace_agents(self, workspace_id: str) -> list[AgentRecord]:
        return await self.adapter.list_by_workspace(workspace_id)

    async def get_agent(self, agent_id: str) -> AgentRecord | None:
        return await self.adapter.get_by_id(agent_id)

    async def get_inference_server(
        self,
        workspace_id: str,
        server_id: str,
    ) -> InferenceServerRecord | None:
        return await self.adapter.get_inference_server(workspace_id, server_id)

    async def create_agent(self, data: AgentCreateInput) -> AgentRecord:
        return await self.adapter.create(data)

    async def create_agents(self, agents: list[AgentCreateInput]) -> list[AgentRecord]:
        return await self.adapter.create_many(agents)

    async def update_agent(
        self,
        agent_id: str,
        updates: AgentUpdateInput,
    ) -> AgentRecord | None:
        return await self.adapter.update(agent_id, updates)

    async def delete_agent(self, agent_id: str) -> bool:
        return await self.adapter.delete(agent_id)
