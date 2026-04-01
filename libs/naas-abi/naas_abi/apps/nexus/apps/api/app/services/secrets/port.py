from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SecretRecord:
    id: str
    workspace_id: str
    key: str
    encrypted_value: str
    description: str
    category: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SecretsPersistencePort(ABC):
    @abstractmethod
    async def list_by_workspace(self, workspace_id: str) -> list[SecretRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_workspace_key(self, workspace_id: str, key: str) -> SecretRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, secret_id: str) -> SecretRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def create(self, record: SecretRecord) -> SecretRecord:
        raise NotImplementedError

    @abstractmethod
    async def save(self, record: SecretRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, secret_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError
