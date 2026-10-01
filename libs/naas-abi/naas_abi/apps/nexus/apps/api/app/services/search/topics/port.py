"""Secondary port: where a workspace's topic definitions are kept."""

from __future__ import annotations

from abc import ABC, abstractmethod

from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import SearchTopic


class SearchTopicStorePort(ABC):
    """Holds a workspace's overrides of built-in topics and its custom topics."""

    @abstractmethod
    async def list(self, workspace_id: str) -> list[SearchTopic]:
        """Every topic stored for the workspace (built-ins are not stored until overridden)."""

    @abstractmethod
    async def save(self, workspace_id: str, topic: SearchTopic, *, user_id: str | None) -> None:
        """Insert or replace the topic with the same id."""

    @abstractmethod
    async def delete(self, workspace_id: str, topic_id: str) -> bool:
        """Remove a stored topic. Returns False when nothing was stored."""

    @abstractmethod
    async def get_disabled_scopes(self, workspace_id: str) -> set[str] | None:
        """Feature and web-engine scopes switched off, or None if the workspace never saved any."""

    @abstractmethod
    async def set_disabled_scopes(
        self, workspace_id: str, scope_ids: set[str], *, user_id: str | None
    ) -> None:
        """Replace the set of switched-off scopes."""
