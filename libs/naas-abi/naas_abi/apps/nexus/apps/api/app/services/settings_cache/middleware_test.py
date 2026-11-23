from __future__ import annotations

import datetime
from dataclasses import replace

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
from starlette.datastructures import Headers


def _build(
    tmp_path,
    ttl: datetime.timedelta = datetime.timedelta(hours=24),
    *,
    cache=None,
    revision=lambda: 1,
    on_list=lambda: None,
):
    calls = {"agents": 0, "skills": 0, "chat": 0}
    app = FastAPI()

    @app.get("/api/agents/")
    def list_agents(workspace_id: str = "ws"):
        calls["agents"] += 1
        on_list()
        return {"workspace": workspace_id, "calls": calls["agents"]}

    @app.patch("/api/agents/{agent_id}")
    def update_agent(agent_id: str):
        return {"id": agent_id}

    @app.get("/api/skills/")
    def list_skills():
        calls["skills"] += 1
        return {"calls": calls["skills"]}

    @app.post("/api/agents/sync")
    def sync_agents():
        return {"reconciled": True}

    @app.post("/api/iam/admin/policies/validate")
    @app.post("/api/iam/admin/simulate")
    def validate():
        return {"valid": True}

    @app.post("/api/iam/admin/attachments")
    def attach():
        return {"attached": True}

    @app.get("/api/skills/broken")
    def broken():
        calls["skills"] += 1
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="boom")

    @app.get("/api/chat/conversations")
    def chat():
        calls["chat"] += 1
        return {"calls": calls["chat"]}

    cache = cache or CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    # The bearer token is the user id in tests; no token means anonymous.
    app.add_middleware(
        SettingsCacheMiddleware,
        cache_resolver=lambda: cache,
        user_resolver=lambda scope: (
            (Headers(scope=scope).get("authorization") or "").removeprefix("Bearer ") or None
        ),
        ttl=ttl,
        authorization_revision=revision,
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


def test_repeated_parameter_order_cannot_alias_different_workspaces(tmp_path):
    client, calls = _build(tmp_path)
    first = _get(client, "/api/agents/?workspace_id=one&workspace_id=two")
    second = _get(client, "/api/agents/?workspace_id=two&workspace_id=one")
    assert first.json()["workspace"] == "two"
    assert second.json()["workspace"] == "one"
    assert second.headers[CACHE_HEADER] == "MISS"
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


def test_a_change_of_policies_invalidates_every_users_cache(tmp_path) -> None:
    # The settings pages (Apps, Agents) list what a policy lets the caller use:
    # an attachment made elsewhere is read again.
    client, calls = _build(tmp_path)
    _get(client, "/api/agents/", user="alice")
    client.post("/api/iam/admin/attachments", headers={"Authorization": "Bearer root"})
    assert _get(client, "/api/agents/", user="alice").headers[CACHE_HEADER] == "MISS"
    assert calls["agents"] == 2


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
        authorization_revision=lambda: 1,
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
        authorization_revision=lambda: 1,
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
        authorization_revision=lambda: 1,
    )
    client = TestClient(app)
    client.get("/api/agents/", headers={CACHE_HEADER: "1"})
    assert client.get("/api/agents/", headers={CACHE_HEADER: "1"}).headers[CACHE_HEADER] == "HIT"

    invalidate_all(cache)

    assert client.get("/api/agents/", headers={CACHE_HEADER: "1"}).headers[CACHE_HEADER] == "MISS"
    assert calls["n"] == 2


# -- entries are the reach of a plain session, per set of groups --------------------------------


def _credentialed(tmp_path):
    """The real resolvers over credentials a stand-in identity middleware sets
    from the ``X-Test-Credential`` header (``kind[:groups][:limited]``)."""
    from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import Credential

    calls = {"agents": 0}
    app = FastAPI()

    @app.get("/api/agents/")
    def list_agents():
        calls["agents"] += 1
        return {"calls": calls["agents"]}

    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    app.add_middleware(
        SettingsCacheMiddleware, cache_resolver=lambda: cache, authorization_revision=lambda: 1
    )

    class Identity:
        def __init__(self, inner):
            self.inner = inner

        async def __call__(self, scope, receive, send):
            raw = Headers(scope=scope).get("x-test-credential")
            if raw:
                kind, groups, limited = (raw.split(":") + ["", ""])[:3]
                scope.setdefault("state", {})["nexus_credential"] = Credential(
                    kind=kind,  # type: ignore[arg-type]
                    user_id="alice",
                    groups=frozenset(g for g in groups.split(",") if g),
                    scope=({"effect": "Allow", "actions": ["*"], "resources": ["ws-1"]},)
                    if limited
                    else None,
                )
            await self.inner(scope, receive, send)

    app.add_middleware(Identity)
    return TestClient(app), calls


def _as(client, credential: str):
    return client.get("/api/agents/", headers={"X-Test-Credential": credential, CACHE_HEADER: "1"})


def test_a_limited_key_never_reads_or_fills_the_sessions_entry(tmp_path) -> None:
    client, calls = _credentialed(tmp_path)

    assert _as(client, "session").headers[CACHE_HEADER] == "MISS"
    assert _as(client, "session").headers[CACHE_HEADER] == "HIT"
    # The same user's key, narrowed to one workspace: answered live, never from the
    # session's entry (which holds everything the user may see)...
    for limited in ("api-key::limited", "session::limited", "coding", "api-key"):
        response = _as(client, limited)
        assert CACHE_HEADER not in response.headers, limited
    live = calls["agents"]
    assert _as(client, "api-key::limited").json()["calls"] == live + 1
    # ...and what the key's request returned fills nothing for the session.
    assert _as(client, "session").headers[CACHE_HEADER] == "HIT"
    assert _as(client, "session").json()["calls"] == 1


def test_sessions_with_other_groups_do_not_share_an_entry(tmp_path) -> None:
    client, _ = _credentialed(tmp_path)

    assert _as(client, "session:sales").headers[CACHE_HEADER] == "MISS"
    assert _as(client, "session:sales").headers[CACHE_HEADER] == "HIT"
    assert _as(client, "session:ops").headers[CACHE_HEADER] == "MISS"
    assert _as(client, "session:ops,sales").headers[CACHE_HEADER] == "MISS"
    assert _as(client, "session:sales").json() == _as(client, "session:sales").json()
    assert _as(client, "session").headers[CACHE_HEADER] == "MISS"


def test_any_credential_still_refreshes_and_invalidates_its_user(tmp_path) -> None:
    client, _ = _credentialed(tmp_path)
    assert _as(client, "session").headers[CACHE_HEADER] == "MISS"
    assert _as(client, "session").headers[CACHE_HEADER] == "HIT"

    refreshed = client.post("/api/settings-cache/refresh", headers={"X-Test-Credential": "api-key"})

    assert refreshed.status_code == 204
    assert _as(client, "session").headers[CACHE_HEADER] == "MISS"


@pytest.mark.parametrize("path", ["/api/iam/admin/policies/validate", "/api/iam/admin/simulate"])
def test_read_like_posts_preserve_resource_caches(tmp_path, path):
    client, _ = _build(tmp_path)
    _get(client, "/api/agents/")
    _get(client, "/api/skills/")

    assert client.post(path).status_code == 200

    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "HIT"
    assert _get(client, "/api/skills/").headers[CACHE_HEADER] == "HIT"


def test_agent_sync_keeps_its_response_and_only_invalidates_agents(tmp_path):
    client, _ = _build(tmp_path)
    _get(client, "/api/agents/")
    _get(client, "/api/skills/")

    assert client.post("/api/agents/sync").json() == {"reconciled": True}

    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "MISS"
    assert _get(client, "/api/skills/").headers[CACHE_HEADER] == "HIT"


@pytest.mark.parametrize("change", ["detach", "policy", "group", "suspend", "delete"])
@pytest.mark.parametrize("source", ["same-service", "other-service", "direct-store"])
def test_cached_permission_is_never_reused_after_revocation(tmp_path, change, source):
    """A real IAM and two SQLite connections; no mocked authorization decisions."""
    from fastapi import HTTPException
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
    from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
    from naas_abi_core.engine.call_context import as_service_account, use_call_context
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import IAMStoreSQLite
    from naas_abi_core.services.iam.IAMService import IAMService
    from naas_abi_core.services.iam.policy import PolicyDocument, Statement

    path = str(tmp_path / "iam.sqlite")
    world = NexusIam(store=IAMStoreSQLite(path))
    person = world.principal("reader")
    with as_service_account("engine"):
        group = world.iam.create_group("Readers")
        world.iam.add_group_member(group.id, person)
        policy = world.iam.create_policy(
            "Roster",
            PolicyDocument(statements=(Statement("Allow", ("nexus:ListAgents",), ("*",)),)),
        )
        holder = group.id if change == "group" else person
        world.iam.attach_policy(policy.id, holder)
    denied = PolicyDocument(statements=(Statement("Deny", ("nexus:ListAgents",), ("*",)),))

    reader = world.iam
    other = IAMService(IAMStoreSQLite(path), revision_check_seconds=60)
    writer = other if source == "other-service" else reader
    app = FastAPI()
    calls = []

    @app.get("/api/agents/")
    def roster():
        with use_call_context(world.context(person)):
            if not reader.authorize("nexus:ListAgents", "abi:nexus:agent/-").allowed:
                raise HTTPException(403)
        calls.append(True)
        return {"agents": ["private-agent"]}

    app.add_middleware(
        SettingsCacheMiddleware,
        cache_resolver=lambda: CacheService(
            adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path / "cache")))]
        ),
        user_resolver=lambda scope: person,
    )
    with world.installed():
        assert runtime.iam() is reader
        client = TestClient(app)
        assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "MISS"
        assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "HIT"
        assert len(calls) == 1

        with as_service_account("engine"):
            if source == "direct-store":
                store = other.store
                if change == "detach":
                    store.detach(policy.id, holder, None)
                elif change == "policy":
                    store.update_policy(replace(policy, document=denied), policy.revision)
                elif change == "group":
                    store.remove_group_member(group.id, person)
                else:
                    record = store.get_principal(person)
                    store.update_principal(
                        replace(record, status="deleted" if change == "delete" else "suspended")
                    )
            elif change == "detach":
                writer.detach_policy(policy.id, holder)
            elif change == "policy":
                writer.update_policy(policy.id, expected_revision=policy.revision, document=denied)
            elif change == "group":
                writer.remove_group_member(group.id, person)
            elif change == "suspend":
                writer.suspend_principal(person)
            else:
                writer.delete_principal(person)

        response = _get(client, "/api/agents/")
        assert response.status_code == 403
        assert response.headers.get(CACHE_HEADER) != "HIT"
        assert len(calls) == 1


def test_an_iam_failure_never_serves_a_previously_cached_answer(tmp_path):
    revision = [1]

    def fresh():
        if revision[0] is None:
            raise RuntimeError("IAM unavailable")
        return revision[0]

    client, calls = _build(tmp_path, revision=fresh)
    _get(client, "/api/agents/")
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "HIT"
    revision[0] = None

    assert CACHE_HEADER not in _get(client, "/api/agents/").headers
    assert calls["agents"] == 2  # the route, with its own guards, ran live


def test_an_unavailable_iam_resolver_also_prevents_cache_fills(tmp_path, monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
    from naas_abi.apps.nexus.apps.api.app.services.settings_cache.middleware import (
        default_authorization_revision,
    )

    monkeypatch.setattr(runtime, "_getter", lambda: None)
    client, calls = _build(tmp_path, revision=default_authorization_revision)
    assert CACHE_HEADER not in _get(client, "/api/agents/").headers
    assert CACHE_HEADER not in _get(client, "/api/agents/").headers
    assert calls["agents"] == 2


def test_a_response_crossing_an_iam_change_does_not_fill_the_new_revision(tmp_path):
    revision = [1]

    def change_during_endpoint():
        revision[0] += 1

    client, calls = _build(tmp_path, revision=lambda: revision[0], on_list=change_during_endpoint)
    _get(client, "/api/agents/")
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "MISS"
    assert calls["agents"] == 2


def test_a_change_while_reading_a_cache_hit_forwards_to_the_live_route(tmp_path, monkeypatch):
    revision = [1]
    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    client, calls = _build(tmp_path, cache=cache, revision=lambda: revision[0])
    _get(client, "/api/agents/")
    original = cache.get

    def revoke_while_reading(key, *args):
        value = original(key, *args)
        revision[0] += 1
        return value

    monkeypatch.setattr(cache, "get", revoke_while_reading)
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "MISS"
    assert calls["agents"] == 2


def test_other_workers_read_invalidation_from_cold_even_with_stale_hot_metadata(tmp_path):
    from naas_abi.apps.nexus.apps.api.app.services.settings_cache.middleware import (
        _GLOBAL_GENERATION_KEY,
    )
    from naas_abi_core.services.cache.CacheService import TIER_HOT

    def worker(name):
        return CacheService(
            adapters=[
                (TIER_HOT, CacheFSAdapter(str(tmp_path / name))),
                (TIER_COLD, CacheFSAdapter(str(tmp_path / "shared"))),
            ]
        )

    first, second = worker("hot1"), worker("hot2")
    a, _ = _build(tmp_path, cache=first)
    b, calls = _build(tmp_path, cache=second)
    _get(b, "/api/agents/")
    _get(b, "/api/skills/")
    # A hot metadata entry left behind by an older worker must never be trusted.
    second.hot.set_json(_GLOBAL_GENERATION_KEY, second.cold.get(_GLOBAL_GENERATION_KEY))
    assert _get(b, "/api/agents/").headers[CACHE_HEADER] == "HIT"

    a.patch("/api/agents/a1")

    assert _get(b, "/api/agents/").headers[CACHE_HEADER] == "MISS"
    assert calls["agents"] == 2
    assert _get(b, "/api/skills/").headers[CACHE_HEADER] == "HIT"
    invalidate_all(first)
    assert _get(b, "/api/skills/").headers[CACHE_HEADER] == "MISS"


def test_overlapping_invalidations_never_reuse_a_generation(tmp_path, monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.settings_cache.middleware import (
        _GLOBAL_GENERATION_KEY,
        _bump_generation,
        _read_generation,
    )

    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    original = cache.cold.set_json
    observed = []

    def overlap(key, value):
        if not observed:
            observed.append(value["v"])
            # A second write completes before the first one's final store.
            observed.append(_bump_generation(cache, key))
        original(key, value)

    monkeypatch.setattr(cache.cold, "set_json", overlap)
    last = _bump_generation(cache, _GLOBAL_GENERATION_KEY)
    assert last != observed[1]
    assert _read_generation(cache, _GLOBAL_GENERATION_KEY) == last


def test_a_failed_refresh_does_not_report_success(tmp_path, monkeypatch):
    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    client, _ = _build(tmp_path, cache=cache)

    def failed(*args, **kwargs):
        raise RuntimeError("cold tier unavailable")

    monkeypatch.setattr(cache.cold, "set_json", failed)
    assert client.post(REFRESH_PATH, headers={"Authorization": "Bearer alice"}).status_code == 503


def test_a_failed_metadata_read_never_trusts_the_hot_response(tmp_path, monkeypatch):
    from naas_abi_core.services.cache.CacheService import TIER_HOT

    cache = CacheService(
        adapters=[
            (TIER_HOT, CacheFSAdapter(str(tmp_path / "hot"))),
            (TIER_COLD, CacheFSAdapter(str(tmp_path / "cold"))),
        ]
    )
    client, calls = _build(tmp_path, cache=cache)
    _get(client, "/api/agents/")
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "HIT"

    def failed(*args, **kwargs):
        raise RuntimeError("cold tier unavailable")

    monkeypatch.setattr(cache.cold, "get", failed)
    assert CACHE_HEADER not in _get(client, "/api/agents/").headers
    assert calls["agents"] == 2


def test_a_response_finishing_after_a_data_mutation_is_not_reused(tmp_path):
    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    client, calls = _build(tmp_path, cache=cache, on_list=lambda: invalidate_all(cache))
    _get(client, "/api/agents/")
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "MISS"
    assert calls["agents"] == 2


def test_a_store_finishing_after_invalidation_cannot_resurrect_an_entry(tmp_path, monkeypatch):
    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    client, calls = _build(tmp_path, cache=cache)
    original = cache.set_json

    def late_store(key, value):
        invalidate_all(cache)
        original(key, value)  # an older in-flight response completes after invalidation

    monkeypatch.setattr(cache, "set_json", late_store)
    _get(client, "/api/agents/")
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "MISS"
    assert calls["agents"] == 2


def test_an_external_revocation_refilters_a_cached_listing(tmp_path, nexus_iam):
    from naas_abi_core.engine.call_context import as_service_account, use_call_context
    from naas_abi_core.services.iam.IAMService import IAMService
    from naas_abi_core.services.iam.policy import PolicyDocument, Statement

    person = nexus_iam.principal("reader")
    resources = ["abi:nexus:agent/first", "abi:nexus:agent/second"]
    with as_service_account("engine"):
        policy_id = nexus_iam.iam.create_policy(
            "Agents",
            PolicyDocument(statements=(Statement("Allow", ("nexus:GetAgent",), tuple(resources)),)),
        ).id
        nexus_iam.iam.attach_policy(policy_id, person)
    app = FastAPI()

    @app.get("/api/agents/")
    def roster():
        with use_call_context(nexus_iam.context(person)):
            return list(nexus_iam.iam.filter("nexus:GetAgent", resources).allowed)

    app.add_middleware(
        SettingsCacheMiddleware,
        cache_resolver=lambda: CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))]),
        user_resolver=lambda scope: person,
    )
    client = TestClient(app)
    assert _get(client, "/api/agents/").json() == resources
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "HIT"
    # No notification or Nexus write request reaches the reader.
    writer = IAMService(nexus_iam.iam.store)
    policy = writer.store.get_policy(policy_id)
    with as_service_account("engine"):
        writer.update_policy(
            policy.id,
            expected_revision=policy.revision,
            document=PolicyDocument(
                statements=(Statement("Allow", ("nexus:GetAgent",), (resources[0],)),)
            ),
        )

    response = _get(client, "/api/agents/")
    assert response.headers[CACHE_HEADER] == "MISS"
    assert response.json() == resources[:1]
    assert _get(client, "/api/agents/").headers[CACHE_HEADER] == "HIT"


@pytest.mark.asyncio
async def test_a_write_is_acknowledged_after_transaction_cleanup_and_invalidation(tmp_path):
    from naas_abi.apps.nexus.apps.api.app.services.settings_cache.middleware import (
        _family_generation_key,
        _read_generation,
    )

    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    key = _family_generation_key("/api/agents")
    before = _read_generation(cache, key)
    committed = False
    acknowledged = []

    async def mutation(scope, receive, send):
        nonlocal committed
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"saved": true}'})
        # As a FastAPI yield dependency: its transaction closes after the response.
        committed = True

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        assert committed
        assert _read_generation(cache, key) != before
        acknowledged.append(message)

    middleware = SettingsCacheMiddleware(mutation, cache_resolver=lambda: cache)
    await middleware({"type": "http", "method": "PATCH", "path": "/api/agents/a1"}, receive, send)
    assert [message["type"] for message in acknowledged] == [
        "http.response.start",
        "http.response.body",
    ]
    assert acknowledged[-1]["body"] == b'{"saved": true}'


@pytest.mark.asyncio
async def test_app_proxy_event_stream_is_forwarded_as_it_arrives(tmp_path):
    cache = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    forwarded = []

    async def stream(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        assert len(forwarded) == 1
        await send({"type": "http.response.body", "body": b"data: first\n\n", "more_body": True})
        assert len(forwarded) == 2
        await send({"type": "http.response.body", "body": b"data: last\n\n"})

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        forwarded.append(message)

    middleware = SettingsCacheMiddleware(stream, cache_resolver=lambda: cache)
    await middleware({"type": "http", "method": "POST", "path": "/api/apps/proxy"}, receive, send)
    assert len(forwarded) == 3
