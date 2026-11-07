"""Search and its topics decide with IAM: viewers read, members refresh the cache,
admins edit the topics, and the search section follows the ``search`` feature.

The real router over a real IAM: ``ws-1`` of ``org-1`` with an owner, an admin, a
member and a viewer, plus a stranger, every role holding every feature unless a
test says otherwise.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (  # noqa: E501
    GraphQueryTripleStoreAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary import (
    search__primary_adapter__FastAPI as search_api,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics import placement
from naas_abi.apps.nexus.apps.api.app.services.search.topics.adapters.primary import (
    topics__primary_adapter__FastAPI as topics_api,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.adapters.secondary.memory import (
    InMemorySearchTopicStore,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.builtin import BUILTIN_TOPICS
from naas_abi.apps.nexus.apps.api.app.services.search.topics.cache import SearchCache
from naas_abi.apps.nexus.apps.api.app.services.search.topics.service import SearchTopicService
from rdflib import Graph

TOPIC = sorted(BUILTIN_TOPICS)[0]
ROLES = ("owner", "admin", "member", "viewer")


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def get(self, key: str, ttl: Any = None) -> Any:
        return self.values[key]

    def set_json(self, key: str, value: Any) -> None:
        self.values[key] = value


@pytest.fixture(autouse=True)
def _forget_placed_caches() -> None:
    placement._PLACED.clear()  # each test has its own IAM: nothing is placed in it yet


def _world(flags: FeatureFlagsConfig | None = None) -> NexusIam:
    everything = list(KNOWN_FEATURE_KEYS)
    flags = flags or FeatureFlagsConfig(
        enabled_features=everything,
        role_baseline=dict.fromkeys(ROLES, everything),
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    for role in ROLES:
        nexus.grant(role, role, scope)
    nexus.user("stranger")
    return nexus


@pytest.fixture
def world():
    nexus = _world()
    with nexus.installed():
        yield nexus


def _client_factory(monkeypatch):
    app = FastAPI()
    app.include_router(search_api.router, prefix="/api/search")
    user = {"id": "member"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id=user["id"])
    service = SearchTopicService(InMemorySearchTopicStore())
    app.dependency_overrides[topics_api.get_search_topic_service] = lambda: service
    app.dependency_overrides[search_api.get_search_service] = lambda: search_api.SearchService()
    cache = SearchCache(MemoryCache())
    monkeypatch.setattr(topics_api, "_SEARCH_CACHE", cache)

    async def scoped(user_id: str, workspace_id: str, graphs=()):
        return GraphQueryTripleStoreAdapter(Graph()), "scope"

    monkeypatch.setattr(topics_api, "_scoped", scoped)

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return as_


@pytest.fixture
def client(world, monkeypatch):
    return _client_factory(monkeypatch)


WS = {"workspace_id": "ws-1"}


def topic_body() -> dict[str, Any]:
    return {key: value for key, value in BUILTIN_TOPICS[TOPIC].to_dict().items() if key != "id"}


@pytest.mark.asyncio
async def test_a_viewer_reads_the_topics_and_cannot_edit_them(client) -> None:
    async with client("viewer") as http:
        listed = await http.get("/api/search/topics", params=WS)
        assert listed.status_code == 200
        assert listed.json()["can_edit"] is False
        assert (await http.get(f"/api/search/topics/{TOPIC}/results", params=WS)).status_code == 200
        detail = await http.get(
            f"/api/search/topics/{TOPIC}/detail", params={**WS, "uri": "http://x/y"}
        )
        # The graph is empty: the entity is unknown (404), which is not a refusal.
        assert detail.status_code == 404
        # Every state change is refused, before the body is read.
        assert (
            await http.put(f"/api/search/topics/{TOPIC}", params=WS, json={})
        ).status_code == 403
        assert (await http.delete(f"/api/search/topics/{TOPIC}", params=WS)).status_code == 403
        scope = await http.put("/api/search/topics/scopes/chat", params=WS, json={"enabled": False})
        assert scope.status_code == 403
        preview = {"workspace_id": "ws-1", "role": "results", "query": "SELECT 1"}
        assert (await http.post("/api/search/topics/preview", json=preview)).status_code == 403
        assert (await http.post("/api/search/topics/cache/refresh", params=WS)).status_code == 403


@pytest.mark.asyncio
async def test_a_member_refreshes_the_cache_but_does_not_edit_topics(client) -> None:
    async with client("member") as http:
        assert (await http.get("/api/search/topics", params=WS)).json()["can_edit"] is False
        assert (await http.post("/api/search/topics/cache/refresh", params=WS)).json() == {
            "refreshed": True
        }
        assert (
            await http.put(f"/api/search/topics/{TOPIC}", params=WS, json=topic_body())
        ).status_code == 403
        assert (await http.delete(f"/api/search/topics/{TOPIC}", params=WS)).status_code == 403


@pytest.mark.asyncio
async def test_an_admin_edits_resets_and_previews_topics(client) -> None:
    async with client("admin") as http:
        assert (await http.get("/api/search/topics", params=WS)).json()["can_edit"] is True
        saved = await http.put(f"/api/search/topics/{TOPIC}", params=WS, json=topic_body())
        assert saved.status_code == 200, saved.text
        assert (await http.delete(f"/api/search/topics/{TOPIC}", params=WS)).status_code == 200
        scope = await http.put("/api/search/topics/scopes/chat", params=WS, json={"enabled": False})
        assert scope.status_code == 200
        preview = {
            "workspace_id": "ws-1",
            "role": "results",
            "query": BUILTIN_TOPICS[TOPIC].results_query,
        }
        assert (await http.post("/api/search/topics/preview", json=preview)).status_code == 200
    async with client("owner") as http:
        assert (await http.get("/api/search/topics", params=WS)).json()["can_edit"] is True


@pytest.mark.asyncio
async def test_the_workspace_of_a_preview_is_the_one_asked_of_iam(client) -> None:
    async with client("admin") as http:
        elsewhere = {"workspace_id": "ws-2", "role": "results", "query": "SELECT 1"}
        assert (await http.post("/api/search/topics/preview", json=elsewhere)).status_code == 403


@pytest.mark.asyncio
async def test_a_stranger_reaches_no_topic(client) -> None:
    async with client("stranger") as http:
        assert (await http.get("/api/search/topics", params=WS)).status_code == 403
        assert (await http.get(f"/api/search/topics/{TOPIC}/results", params=WS)).status_code == 403
        assert (await http.post("/api/search/topics/cache/refresh", params=WS)).status_code == 403
        private = {"workspace_id": "ws-1", "query": "x", "source": "files"}
        assert (await http.post("/api/search/private", json=private)).status_code == 403


@pytest.mark.asyncio
async def test_private_search_needs_the_workspace_it_names(client) -> None:
    private = {"workspace_id": "ws-1", "query": "x", "source": "files"}
    for user in ROLES:
        async with client(user) as http:
            assert (await http.post("/api/search/private", json=private)).status_code == 200, user
    async with client("member") as http:
        other = {**private, "workspace_id": "ws-2"}
        assert (await http.post("/api/search/private", json=other)).status_code == 403


@pytest.mark.asyncio
async def test_the_signed_in_public_lookups_need_no_workspace(client) -> None:
    async with client("stranger") as http:
        assert (await http.post("/api/search/", json={"query": "x"})).status_code == 200
        assert (await http.get("/api/search/topics/contract")).status_code == 200


@pytest.mark.asyncio
async def test_the_search_section_follows_the_feature(monkeypatch) -> None:
    # The deployment's defaults give the search section to admins and owners only.
    nexus = _world(FeatureFlagsConfig())
    with nexus.installed():
        client = _client_factory(monkeypatch)
        async with client("viewer") as http:
            denied = await http.get("/api/search/topics", params=WS)
            assert denied.status_code == 403
            assert "feature" in denied.json()["detail"]
            private = {"workspace_id": "ws-1", "query": "x", "source": "files"}
            assert (await http.post("/api/search/private", json=private)).status_code == 403
        async with client("admin") as http:
            assert (await http.get("/api/search/topics", params=WS)).status_code == 200
