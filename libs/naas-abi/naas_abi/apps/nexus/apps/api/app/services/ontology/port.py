from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OntologyConfigRecord:
    id: str
    workspace_id: str
    path: str
    name: str
    module_name: str
    submodule_name: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class OntologyConfigCreateInput:
    workspace_id: str
    path: str
    name: str
    module_name: str
    submodule_name: str | None = None
    enabled: bool = True


@dataclass
class OntologyConfigUpdateInput:
    name: str | None = None
    module_name: str | None = None
    submodule_name: str | None = None
    enabled: bool | None = None


class OntologyPersistencePort(ABC):
    @abstractmethod
    async def list_by_workspace(self, workspace_id: str) -> list[OntologyConfigRecord]:
        pass

    @abstractmethod
    async def get(self, workspace_id: str, path: str) -> OntologyConfigRecord | None:
        pass

    @abstractmethod
    async def create(self, data: OntologyConfigCreateInput) -> OntologyConfigRecord:
        pass

    @abstractmethod
    async def create_many(
        self, configs: list[OntologyConfigCreateInput]
    ) -> list[OntologyConfigRecord]:
        pass

    @abstractmethod
    async def update(
        self, workspace_id: str, path: str, updates: OntologyConfigUpdateInput
    ) -> OntologyConfigRecord | None:
        pass

    @abstractmethod
    async def delete(self, workspace_id: str, path: str) -> bool:
        pass
