from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.search.topics.port import SearchTopicStorePort
from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import SearchTopic


class InMemorySearchTopicStore(SearchTopicStorePort):
    def __init__(self) -> None:
        self._topics: dict[str, dict[str, SearchTopic]] = {}

    async def list(self, workspace_id: str) -> list[SearchTopic]:
        return list(self._topics.get(workspace_id, {}).values())

    async def save(self, workspace_id: str, topic: SearchTopic, *, user_id: str | None) -> None:
        self._topics.setdefault(workspace_id, {})[topic.id] = topic

    async def delete(self, workspace_id: str, topic_id: str) -> bool:
        return self._topics.get(workspace_id, {}).pop(topic_id, None) is not None
