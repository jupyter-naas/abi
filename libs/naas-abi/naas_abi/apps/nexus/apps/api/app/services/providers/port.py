from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderAvailabilityPort(ABC):
    @abstractmethod
    async def list_workspace_ids_for_user(self, user_id: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def list_secret_keys_for_workspaces(self, workspace_ids: list[str]) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    async def list_environment_keys(self, key_names: list[str]) -> set[str]:
        raise NotImplementedError
