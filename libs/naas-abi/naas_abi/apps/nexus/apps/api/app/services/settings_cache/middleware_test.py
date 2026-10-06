from __future__ import annotations

import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.settings_cache.middleware import (
    CACHE_HEADER,
    REFRESH_PATH,
    SettingsCacheMiddleware,
    invalidate_all,
)
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import CacheFSAdapter
from naas_abi_core.services.cache.CacheService import TIER_COLD, CacheService


def _build(tmp_path, ttl: datetime.timedelta = datetime.timedelta(hours=24)):
    calls = {"agents": 0, "skills": 0, "chat": 0}
    app = FastAPI()

    @app.get("/api/agents/")
    def list_agents(workspace_id: str = "ws"):
        calls["agents"] += 1
        return {"workspace": workspace_id, "calls": calls["agents"]}

    @app.patch("/api/agents/{agent_id}")
    def update_agent(agent_id: str):
        return {"id": agent_id}

    @app.get("/api/skills/broken")
    def broken():
        calls["skills"] += 1
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="boom")

    @app.get("/api/chat/conversations")
    def chat():
        calls["chat"] += 1
        return {"calls": calls["chat"]}

    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    # The bearer token is the user id in tests; no token means anonymous.
    app.add_middleware(
        SettingsCacheMiddleware,
        cache_resolver=lambda: cache,
        user_resolver=lambda headers: (
            (headers.get("authorization") or "").removeprefix("Bearer ") or None
        ),
        ttl=ttl,
    )
    return TestClient(app), calls


def _get(client: TestClient, path: str, user: str | None = "alice", opt_in: bool = True):
    headers = {}
    if user:
        headers["Authorization"] = f"Bearer {user}"
    if opt_in:
        headers[CACHE_HEADER] = "1"
    return client.get(path, headers=headers)


def test_opted_in_get_is_served_from_cache_on_second_call(tmp_path) -> None:
    client, calls = _build(tmp_path)
    first = _get(client, "/api/agents/?workspace_id=ws1")
    second = _get(client, "/api/agents/?workspace_id=ws1")
    assert first.headers[CACHE_HEADER] == "MISS"
    assert second.headers[CACHE_HEADER] == "HIT"
    assert second.json() == first.json()
    assert calls["agents"] == 1


def test_query_string_is_part_of_the_key(tmp_path) -> None:
    client, calls = _build(tmp_path)
    _get(client, "/api/agents/?workspace_id=ws1")
    _get(client, "/api/agents/?workspace_id=ws2")
    assert calls["agents"] == 2


def test_requests_without_opt_in_header_are_never_cached(tmp_path) -> None:
    client, calls = _build(tmp_path)
    _get(client, "/api/agents/", opt_in=False)
    response = _get(client, "/api/agents/", opt_in=False)
    assert CACHE_HEADER not in response.headers
    assert calls["agents"] == 2


def test_anonymous_requests_are_never_cached(tmp_path) -> None:
    client, calls = _build(tmp_path)
    _get(client, "/api/agents/", user=None)
    _get(client, "/api/agents/", user=None)
    assert calls["agents"] == 2


def test_users_do_not_share_cached_answers(tmp_path) -> None:
    client, calls = _build(tmp_path)
    _get(client, "/api/agents/", user="alice")
    response = _get(client, "/api/agents/", user="bob")
    assert response.headers[CACHE_HEADER] == "MISS"
    assert calls["agents"] == 2


def test_paths_outside_settings_routes_are_not_cached(tmp_path) -> None:
    client, calls = _build(tmp_path)
    _get(client, "/api/chat/conversations")
    _get(client, "/api/chat/conversations")
    assert calls["chat"] == 2


def test_error_responses_are_not_cached(tmp_path) -> None:
    client, calls = _build(tmp_path)
    _get(client, "/api/skills/broken")
    _get(client, "/api/skills/broken")
    assert calls["skills"] == 2


def test_successful_write_invalidates_every_users_cache(tmp_path) -> None:
    client, calls = _build(tmp_path)
    _get(client, "/api/agents/", user="alice")
    _get(client, "/api/agents/", user="bob")
    client.patch("/api/agents/a1", headers={"Authorization": "Bearer bob"})
    assert _get(client, "/api/agents/", user="alice").headers[CACHE_HEADER] == "MISS"
    assert calls["agents"] == 3


def test_refresh_drops_only_the_callers_cache(tmp_path) -> None:
    client, calls = _build(tmp_path)
    _get(client, "/api/agents/", user="alice")
    _get(client, "/api/agents/", user="bob")
    response = client.post(REFRESH_PATH, headers={"Authorization": "Bearer alice"})
    assert response.status_code == 204
    assert _get(client, "/api/agents/", user="alice").headers[CACHE_HEADER] == "MISS"
    assert _get(client, "/api/agents/", user="bob").headers[CACHE_HEADER] == "HIT"
    # The refreshed answer is cached again for the next call.
    assert _get(client, "/api/agents/", user="alice").headers[CACHE_HEADER] == "HIT"


def test_refresh_requires_a_user(tmp_path) -> None:
    client, _ = _build(tmp_path)
    assert client.post(REFRESH_PATH).status_code == 401


def test_expired_entries_are_recomputed(tmp_path) -> None:
    client, calls = _build(tmp_path, ttl=datetime.timedelta(seconds=-1))
    _get(client, "/api/agents/")
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "MISS"
    assert calls["agents"] == 2


def test_a_broken_cache_never_breaks_the_request(tmp_path) -> None:
    app = FastAPI()

    @app.get("/api/agents/")
    def list_agents():
        return {"ok": True}

    class BrokenCache:
        def get(self, *args, **kwargs):
            raise RuntimeError("down")

        def set_json(self, *args, **kwargs):
            raise RuntimeError("down")

        def hot_available(self) -> bool:
            return False

    app.add_middleware(
        SettingsCacheMiddleware,
        cache_resolver=lambda: BrokenCache(),
        user_resolver=lambda headers: "alice",
    )
    response = TestClient(app).get("/api/agents/", headers={CACHE_HEADER: "1"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_writes_outside_settings_routes_do_not_invalidate(tmp_path, method) -> None:
    client, calls = _build(tmp_path)
    _get(client, "/api/agents/")
    getattr(client, method)("/api/chat/conversations", headers={"Authorization": "Bearer alice"})
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "HIT"
    assert calls["agents"] == 1


def test_cached_answers_still_carry_cors_headers(tmp_path) -> None:
    """Registered before CORS (so inside it), as in main.py: HITs go out through CORS."""
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI()

    @app.get("/api/agents/")
    def list_agents():
        return {"ok": True}

    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    app.add_middleware(
        SettingsCacheMiddleware,
        cache_resolver=lambda: cache,
        user_resolver=lambda headers: "alice",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://web.test"],
        allow_headers=["Authorization", CACHE_HEADER],
        expose_headers=[CACHE_HEADER],
    )
    client = TestClient(app)
    headers = {"Origin": "http://web.test", CACHE_HEADER: "1"}
    client.get("/api/agents/", headers=headers)
    hit = client.get("/api/agents/", headers=headers)
    assert hit.headers[CACHE_HEADER] == "HIT"
    assert hit.headers["access-control-allow-origin"] == "http://web.test"
    assert CACHE_HEADER.lower() in hit.headers["access-control-expose-headers"].lower()


def test_invalidate_all_drops_every_entry(tmp_path) -> None:
    """Called when ABI starts, so a restart never serves answers from before it."""
    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    calls = {"n": 0}
    app = FastAPI()

    @app.get("/api/agents/")
    def list_agents():
        calls["n"] += 1
        return {"n": calls["n"]}

    app.add_middleware(
        SettingsCacheMiddleware,
        cache_resolver=lambda: cache,
        user_resolver=lambda headers: "alice",
    )
    client = TestClient(app)
    client.get("/api/agents/", headers={CACHE_HEADER: "1"})
    assert client.get("/api/agents/", headers={CACHE_HEADER: "1"}).headers[CACHE_HEADER] == "HIT"

    invalidate_all(cache)

    assert client.get("/api/agents/", headers={CACHE_HEADER: "1"}).headers[CACHE_HEADER] == "MISS"
    assert calls["n"] == 2
