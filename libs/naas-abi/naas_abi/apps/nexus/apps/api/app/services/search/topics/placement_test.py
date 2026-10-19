"""A workspace's search cache is placed in it, and in no other."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam import placements
from naas_abi.apps.nexus.apps.api.app.services.search.topics import placement
from naas_abi.apps.nexus.apps.api.app.services.search.topics.cache import (
    SearchCache,
    workspace_prefix,
)


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str, ttl: object = None) -> object:
        return self.values[key]

    def set_json(self, key: str, value: object) -> None:
        self.values[key] = value


@pytest.fixture(autouse=True)
def _forget_placed_workspaces():
    """Each test has its own IAM: nothing is placed in it yet."""
    placement._PLACED.clear()
    yield
    placement._PLACED.clear()


def cache_keys(workspace_id: str) -> list[str]:
    memory = MemoryCache()
    cache = SearchCache(memory)
    cache.store(
        cache.key(workspace_id, scope="s", topic={"id": "t"}, request={"q": "x"}),
        {"total": 1},
    )
    return sorted(memory.values)  # the entry and the workspace's generation


def test_every_key_of_a_workspace_starts_with_its_prefix() -> None:
    keys = cache_keys("ws-1")
    assert len(keys) == 2
    assert all(key.startswith(workspace_prefix("ws-1")) for key in keys)


def test_no_workspaces_prefix_starts_another() -> None:
    ids = ["ws-1", "ws-10", "ws-1-2", "ws-1_", "WS-1", "a", "ab"]
    for one in ids:
        for other in ids:
            if one != other:
                assert not workspace_prefix(other).startswith(workspace_prefix(one))


@pytest.mark.asyncio
async def test_existing_workspaces_come_from_the_workspaces_table() -> None:
    class Db:
        async def execute(self, _query):
            return [("ws-1",), ("ws-2",)]

    assert placement.search_caches in placements.SOURCES
    found = list(await placement.search_caches(Db()))
    assert [p.workspace for p in found] == ["ws-1", "ws-2"]


@pytest.mark.asyncio
async def test_a_placed_cache_covers_the_workspaces_keys_only(team) -> None:
    await placement.ensure_search_cache_placed("ws-1")

    def workspace_of(key: str) -> str | None:
        found = team.iam.placement_of("cache", key)
        return found.workspace if found else None

    assert all(workspace_of(key) == "ws-1" for key in cache_keys("ws-1"))
    assert all(workspace_of(key) is None for key in cache_keys("ws-2"))
    assert workspace_of("search_topics_generation_x") is None
