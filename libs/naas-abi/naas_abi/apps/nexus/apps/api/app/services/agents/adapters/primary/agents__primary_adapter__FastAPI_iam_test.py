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

APPS = "naas_abi.agents.AppsAgent/AppsAgent"
FILES = "naas_abi.agents.FilesAgent/FilesAgent"


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
        _agent("elsewhere", workspace="ws-2"),
    )
    synced: list[str] = []

    async def reconcile(agent_service, workspace_id, agent_list, *args, **kwargs):
        synced.append(workspace_id)
        return agent_list

    async def no_remote():
        return []

    monkeypatch.setattr(adapter, "_get_agent_class_registry", lambda: {})
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

    return SimpleNamespace(as_=as_, agents=agents, synced=synced)


@pytest.mark.asyncio
async def test_every_role_of_the_workspace_reads_the_roster_and_a_stranger_does_not(world) -> None:
    for role in ("viewer", "member", "admin", "owner"):
        async with world.as_(role) as http:
            response = await http.get("/?workspace_id=ws-1")
            assert response.status_code == 200, role
            assert {a["id"] for a in response.json()} >= {"plain", "files"}
    async with world.as_("stranger") as http:
        assert (await http.get("/?workspace_id=ws-1")).status_code == 403
        assert (await http.get("/plain")).status_code == 403


@pytest.mark.asyncio
async def test_an_office_agent_follows_the_features_the_caller_holds(world) -> None:
    # Members and viewers hold no "apps" feature by default: the Apps agent is
    # not offered to them, nor addressable by id; admins get it.
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
        assert {a["id"] for a in response.json()} >= {"plain", "files"}
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
