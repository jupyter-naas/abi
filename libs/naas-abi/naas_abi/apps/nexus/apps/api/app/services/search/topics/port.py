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
