from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AgentRecord:
    id: str
    workspace_id: str
    name: str
    class_name: str | None
    description: str | None
    system_prompt: str | None
    model_id: str | None
    provider: str | None
    logo_url: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class InferenceServerRecord:
    id: str
    workspace_id: str
    name: str
    type: str
    endpoint: str
    api_key: str | None


@dataclass
class AgentCreateInput:
    workspace_id: str
    name: str
    class_name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_id: str | None = None
    provider: str | None = None
    logo_url: str | None = None
    enabled: bool = False


@dataclass
class AgentUpdateInput:
    name: str | None = None
    class_name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_id: str | None = None
    enabled: bool | None = None
    model: str | None = None


class AgentPersistencePort(ABC):
    @abstractmethod
    async def list_by_workspace(self, workspace_id: str) -> list[AgentRecord]:
        pass

    @abstractmethod
    async def get_by_id(self, agent_id: str) -> AgentRecord | None:
        pass

    @abstractmethod
    async def get_inference_server(
        self, workspace_id: str, server_id: str
    ) -> InferenceServerRecord | None:
        pass

    @abstractmethod
    async def create(self, data: AgentCreateInput) -> AgentRecord:
        pass

    @abstractmethod
    async def create_many(self, agents: list[AgentCreateInput]) -> list[AgentRecord]:
        pass

    @abstractmethod
    async def update(self, agent_id: str, updates: AgentUpdateInput) -> AgentRecord | None:
        pass

    @abstractmethod
    async def delete(self, agent_id: str) -> bool:
        pass
