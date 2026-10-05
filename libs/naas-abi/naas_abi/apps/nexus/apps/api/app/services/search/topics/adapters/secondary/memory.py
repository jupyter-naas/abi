from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.search.topics.port import SearchTopicStorePort
from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import SearchTopic


class InMemorySearchTopicStore(SearchTopicStorePort):
    def __init__(self) -> None:
        self._topics: dict[str, dict[str, SearchTopic]] = {}
        self._disabled: dict[str, set[str]] = {}

    async def list(self, workspace_id: str) -> list[SearchTopic]:
        return list(self._topics.get(workspace_id, {}).values())

    async def save(self, workspace_id: str, topic: SearchTopic, *, user_id: str | None) -> None:
        self._topics.setdefault(workspace_id, {})[topic.id] = topic

    async def delete(self, workspace_id: str, topic_id: str) -> bool:
        return self._topics.get(workspace_id, {}).pop(topic_id, None) is not None

    async def get_disabled_scopes(self, workspace_id: str) -> set[str] | None:
        stored = self._disabled.get(workspace_id)
        return None if stored is None else set(stored)

    async def set_disabled_scopes(
        self, workspace_id: str, scope_ids: set[str], *, user_id: str | None
    ) -> None:
        self._disabled[workspace_id] = set(scope_ids)
