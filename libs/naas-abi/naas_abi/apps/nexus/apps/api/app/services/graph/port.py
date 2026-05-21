from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GraphConfigRecord:
    id: str
    workspace_id: str
    graph_uri: str
    name: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class GraphConfigCreateInput:
    workspace_id: str
    graph_uri: str
    name: str
    enabled: bool = True


@dataclass
class GraphConfigUpdateInput:
    name: str | None = None
    enabled: bool | None = None


class GraphPersistencePort(ABC):
    @abstractmethod
    async def list_by_workspace(self, workspace_id: str) -> list[GraphConfigRecord]:
        pass

    @abstractmethod
    async def get(self, workspace_id: str, graph_uri: str) -> GraphConfigRecord | None:
        pass

    @abstractmethod
    async def create(self, data: GraphConfigCreateInput) -> GraphConfigRecord:
        pass

    @abstractmethod
    async def create_many(self, configs: list[GraphConfigCreateInput]) -> list[GraphConfigRecord]:
        pass

    @abstractmethod
    async def update(
        self, workspace_id: str, graph_uri: str, updates: GraphConfigUpdateInput
    ) -> GraphConfigRecord | None:
        pass

    @abstractmethod
    async def delete(self, workspace_id: str, graph_uri: str) -> bool:
        pass
