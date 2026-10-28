"""Who may list, sync, change and read agents: IAM decides, on the real router."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary import (
    agents__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope

APPS = "naas_abi.agents.AppsAgent/AppsAgent"
FILES = "naas_abi.agents.FilesAgent/FilesAgent"
# Two agents of one module, P: ``agent/acme.p/A`` and ``agent/acme.p/B``.
AGENT_A = "acme.p.agents.A/AAgent"
AGENT_B = "acme.p.agents.B/BAgent"
WS = "abi:org-1:ws-1"


def _agent(agent_id: str, workspace: str = "ws-1", class_name: str | None = None) -> AgentRecord:
    now = datetime(2026, 10, 1)
    return AgentRecord(
        id=agent_id,
        workspace_id=workspace,
        name=agent_id,
        description="",
        enabled=True,
        class_name=class_name,
        module_path=None,
        system_prompt=None,
        model_id=None,
        provider="abi",
        logo_url=None,
        created_at=now,
        updated_at=now,
    )


class FakeAgents:
    def __init__(self, *records: AgentRecord) -> None:
        self.records = {r.id: r for r in records}
        self.calls: list[str] = []

    async def list_workspace_agents(self, workspace_id):
        return [r for r in self.records.values() if r.workspace_id == workspace_id]

    async def get_agent(self, agent_id):
        return self.records.get(agent_id)

    async def create_agent(self, data):
        self.calls.append("create")
        record = _agent(f"new-{len(self.records)}", data.workspace_id)
        self.records[record.id] = record
        return record

    async def update_agent(self, agent_id, updates):
        self.calls.append("update")
        return self.records[agent_id]

    async def delete_agent(self, agent_id):
        self.calls.append("delete")
        return self.records.pop(agent_id, None) is not None


@pytest.fixture
def world(team, monkeypatch):
    agents = FakeAgents(
        _agent("plain"),
        _agent("apps", class_name=APPS),
        _agent("files", class_name=FILES),
        _agent("a", class_name=AGENT_A),
        _agent("b", class_name=AGENT_B),
        _agent("elsewhere", workspace="ws-2"),
    )
    synced: list[str] = []

    async def reconcile(agent_service, workspace_id, agent_list, *args, **kwargs):
        synced.append(workspace_id)
        return agent_list

    async def no_remote():
        return []

    monkeypatch.setattr(adapter, "_get_agent_class_registry", lambda: {})
    monkeypatch.setattr(
        adapter,
        "_agent_class_modules",
        {APPS: "naas_abi", FILES: "naas_abi", AGENT_A: "acme.p", AGENT_B: "acme.p"},
    )
    monkeypatch.setattr(adapter, "_reconcile_workspace_agents", reconcile)
    monkeypatch.setattr(adapter, "_discovered_remote_agents", no_remote)
    app = FastAPI()
    app.include_router(adapter.router)
    app.dependency_overrides[adapter.get_agent_service] = lambda: agents
    user = {"id": "member"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(**user)

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return SimpleNamespace(as_=as_, agents=agents, synced=synced, team=team)


def _scope(module: str, name: str) -> ModuleScope:
    return ModuleScope("agent", module, name)


@pytest.mark.asyncio
async def test_every_role_of_the_workspace_reads_the_roster_and_a_stranger_does_not(world) -> None:
    # Zero trust: viewers and members see no module's agent, naas_abi's own
    # included, until a policy grants it; admins and owners see them all.
    for role in ("viewer", "member"):
        async with world.as_(role) as http:
            response = await http.get("/?workspace_id=ws-1")
            assert response.status_code == 200, role
            assert {a["id"] for a in response.json()} == {"plain"}
    for role in ("admin", "owner"):
        async with world.as_(role) as http:
            response = await http.get("/?workspace_id=ws-1")
            assert {a["id"] for a in response.json()} == {"plain", "apps", "files", "a", "b"}
    async with world.as_("stranger") as http:
        assert (await http.get("/?workspace_id=ws-1")).status_code == 403
        assert (await http.get("/plain")).status_code == 403


@pytest.mark.asyncio
async def test_a_grant_of_one_agent_lists_that_one_and_leaves_the_other_refused(world) -> None:
    world.team.allow_scope("member", _scope("acme.p", "AAgent"), WS)
    async with world.as_("member") as http:
        ids = {a["id"] for a in (await http.get("/?workspace_id=ws-1")).json()}
        assert ids == {"plain", "a"}
        assert (await http.get("/a")).status_code == 200
        assert (await http.get("/b")).status_code == 404
    async with world.as_("viewer") as http:
        assert (await http.get("/a")).status_code == 404


@pytest.mark.asyncio
async def test_an_office_agent_follows_the_features_the_caller_holds(world) -> None:
    # Members hold no "apps" feature by default: granted both office agents,
    # the Apps agent is still not offered to them, nor addressable by id.
    world.team.allow_scope("member", _scope("naas_abi", "AppsAgent"), WS)
    world.team.allow_scope("member", _scope("naas_abi", "FilesAgent"), WS)
    async with world.as_("member") as http:
        ids = {a["id"] for a in (await http.get("/?workspace_id=ws-1")).json()}
        assert "apps" not in ids and "files" in ids
        assert (await http.get("/apps")).status_code == 404
        assert (await http.get("/files")).status_code == 200
    async with world.as_("admin") as http:
        ids = {a["id"] for a in (await http.get("/?workspace_id=ws-1")).json()}
        assert {"apps", "files"} <= ids
        assert (await http.get("/apps")).status_code == 200


@pytest.mark.asyncio
async def test_an_agent_of_another_workspace_is_out_of_reach(world) -> None:
    async with world.as_("admin") as http:
        assert (await http.get("/elsewhere")).status_code == 403
        assert (await http.patch("/elsewhere", json={"name": "x"})).status_code == 403
        assert (await http.delete("/elsewhere")).status_code == 403
    assert world.agents.calls == []


@pytest.mark.asyncio
async def test_a_viewer_cannot_change_agents(world) -> None:
    async with world.as_("viewer") as http:
        assert (await http.post("/", json={"workspace_id": "ws-1", "name": "n"})).status_code == 403
        assert (await http.patch("/plain", json={"enabled": False})).status_code == 403
        assert (await http.delete("/plain")).status_code == 403
    assert world.agents.calls == []


@pytest.mark.asyncio
async def test_changing_agents_needs_the_agents_section_and_a_writer(world) -> None:
    # A member writes, but the agents settings section is off for members.
    async with world.as_("member") as http:
        refused = await http.patch("/plain", json={"enabled": False})
        assert refused.status_code == 403
        assert "not available" in refused.json()["detail"]
    for role in ("admin", "owner"):
        async with world.as_(role) as http:
            assert (
                await http.post("/", json={"workspace_id": "ws-1", "name": "n"})
            ).status_code == 200
            assert (await http.patch("/plain", json={"enabled": False})).status_code == 200
    assert world.agents.calls == ["create", "update", "create", "update"]


@pytest.mark.asyncio
async def test_a_deleted_agent_is_gone_for_admins_only(world) -> None:
    async with world.as_("member") as http:
        assert (await http.delete("/plain")).status_code == 403
    async with world.as_("admin") as http:
        assert (await http.delete("/plain")).json() == {"status": "deleted"}
        assert (await http.delete("/plain")).status_code == 404


@pytest.mark.asyncio
async def test_sync_reconciles_for_writers_and_only_lists_for_viewers(world) -> None:
    async with world.as_("viewer") as http:
        response = await http.post("/sync?workspace_id=ws-1")
        assert response.status_code == 200
        assert {a["id"] for a in response.json()} == {"plain"}
    assert world.synced == []
    for role in ("member", "admin"):
        async with world.as_(role) as http:
            assert (await http.post("/sync?workspace_id=ws-1")).status_code == 200
    assert world.synced == ["ws-1", "ws-1"]
    async with world.as_("stranger") as http:
        assert (await http.post("/sync?workspace_id=ws-1")).status_code == 403
    assert world.synced == ["ws-1", "ws-1"]


@pytest.mark.asyncio
async def test_no_workspace_lists_nothing(world) -> None:
    async with world.as_("viewer") as http:
        assert (await http.get("/")).json() == []
        assert (await http.post("/sync")).json() == []


@pytest.mark.asyncio
async def test_a_turn_in_a_fresh_workspace_seeds_its_roster_and_runs_for_an_owner(
    team, monkeypatch
) -> None:
    """A workspace whose roster no listing reconciled has no rows: the turn seeds
    it, so an owner (who holds every module scope) is not refused every agent."""
    from naas_abi.apps.nexus.apps.api.app.core.agent_feature_access import bind_usable_agents
    from naas_abi_core.services.agent.context import agent_workspace_enabled_class_names

    agents = FakeAgents()
    seeded = _agent("seeded-a", class_name=AGENT_A)

    async def reconcile(*, agent_service, workspace_id, agent_list, **_):
        assert agent_list == []
        agent_service.records[seeded.id] = seeded
        return [seeded]

    async def no_remote():
        return []

    monkeypatch.setattr(adapter, "_reconcile_workspace_agents", reconcile)
    monkeypatch.setattr(adapter, "_discovered_remote_agents", no_remote)
    monkeypatch.setattr(adapter, "_get_agent_class_registry", lambda: {})
    monkeypatch.setattr(adapter, "_agent_class_modules", {AGENT_A: "acme.p"})
    token = agent_workspace_enabled_class_names.set(None)
    try:
        allowed = await bind_usable_agents(agents, "owner", "ws-1")
        assert allowed == {AGENT_A}
        # Seeded once: the next turn reads the rows.
        assert await adapter.workspace_roster(agents, "ws-1") == [seeded]
        # A member without the scope runs nothing, roster or not.
        assert await bind_usable_agents(agents, "member", "ws-1") == frozenset()
    finally:
        agent_workspace_enabled_class_names.reset(token)


# -- the workspace's set and what it turned off ------------------------------------------


@pytest.mark.asyncio
async def test_a_workspace_lists_only_the_module_agents_of_its_set(world) -> None:
    world.team.platform_admin("root")
    world.team.put_set("org-1", "ws-1", modules=["agent/acme.p/AAgent"])
    for who in ("admin", "owner", "root"):
        async with world.as_(who) as http:
            ids = {a["id"] for a in (await http.get("/?workspace_id=ws-1")).json()}
            # An agent the workspace built is its own, never a module's.
            assert ids == {"plain", "a"}, who
            assert (await http.get("/b")).status_code == 404, who


@pytest.mark.asyncio
async def test_no_module_agent_outside_the_set_is_turned_on_or_added(world) -> None:
    world.team.put_set("org-1", "ws-1", modules=["acme.p"])
    async with world.as_("admin") as http:
        refused = await http.patch("/apps", json={"enabled": True})
        assert refused.status_code == 403
        assert "not in the workspace's set" in refused.json()["detail"]
        added = {"workspace_id": "ws-1", "name": "n", "class_name": FILES, "provider": "abi"}
        assert (await http.post("/", json=added)).status_code == 403
        # Off, always; one of the set, on; one the workspace builds, added.
        assert (await http.patch("/apps", json={"enabled": False})).status_code == 200
        assert (await http.patch("/a", json={"enabled": True})).status_code == 200
        assert (await http.post("/", json={"workspace_id": "ws-1", "name": "n"})).status_code == 200


@pytest.mark.asyncio
async def test_an_agent_turned_off_is_listed_to_who_turns_it_on_alone(world) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.agents.visibility import AgentsVisibility
    from naas_abi.apps.nexus.apps.api.app.services.visibility.testing import (
        visibility_installed,
    )

    world.team.allow_scope("member", _scope("acme.p", "AAgent"), WS)
    world.agents.records["a"].enabled = False
    world.agents.records["plain"].enabled = False

    async def rows(workspace_id):
        return await world.agents.list_workspace_agents(workspace_id)

    with visibility_installed({"agent": AgentsVisibility(rows)}):
        async with world.as_("member") as http:
            assert (await http.get("/?workspace_id=ws-1")).json() == []
            assert (await http.get("/a")).status_code == 404
            assert (await http.get("/plain")).status_code == 404
        async with world.as_("admin") as http:
            listed = {a["id"]: a["enabled"] for a in (await http.get("/?workspace_id=ws-1")).json()}
            assert listed["a"] is False and listed["plain"] is False
            assert (await http.get("/a")).status_code == 200
