"""Who may list, create, change, use and delete skills: IAM decides, on the real router."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.skills.adapters.primary import (
    skills__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.skills.port import SkillRecord
from naas_abi.apps.nexus.apps.api.app.services.skills.service import SkillService


def _skill(
    skill_id: str, *, workspace: str = "ws-1", scope: str = "workspace", user_id: str = "owner"
):
    now = datetime(2026, 10, 1)
    return SkillRecord(
        id=skill_id,
        workspace_id=workspace,
        organization_id=None,
        user_id=user_id,
        name=skill_id,
        slug=skill_id,
        description="",
        prompt="do it",
        scope=scope,
        enabled=True,
        last_used_at=None,
        created_at=now,
        updated_at=now,
    )


class MemorySkills:
    """The persistence port, in memory."""

    def __init__(self, *records: SkillRecord) -> None:
        self.records = {r.id: r for r in records}

    async def list_visible(self, workspace_id, user_id):
        return [
            r
            for r in self.records.values()
            if r.workspace_id == workspace_id and (r.scope != "user" or r.user_id == user_id)
        ]

    async def get_by_id(self, skill_id):
        return self.records.get(skill_id)

    async def get_visible_by_slug(self, workspace_id, user_id, slug):
        return next(
            (r for r in await self.list_visible(workspace_id, user_id) if r.slug == slug), None
        )

    async def create(self, data):
        record = replace(
            _skill(data.slug, workspace=data.workspace_id, scope=data.scope, user_id=data.user_id)
        )
        self.records[record.id] = record
        return record

    async def update(self, skill_id, updates):
        record = replace(self.records[skill_id], name=updates.name or self.records[skill_id].name)
        self.records[skill_id] = record
        return record

    async def mark_used(self, skill_id, now):
        record = replace(self.records[skill_id], last_used_at=now)
        self.records[skill_id] = record
        return record

    async def delete(self, skill_id):
        return self.records.pop(skill_id, None) is not None


@pytest.fixture
def world(team):
    store = MemorySkills(
        _skill("shared"),
        _skill("mine", scope="user", user_id="member"),
        _skill("other-ws", workspace="ws-2"),
    )
    service = SkillService(store)
    app = FastAPI()
    app.include_router(adapter.router)
    app.dependency_overrides[adapter.get_skill_service] = lambda: service
    user = {"id": "member"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(**user)

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return SimpleNamespace(as_=as_, store=store)


NEW = {"workspace_id": "ws-1", "name": "Brief", "prompt": "Write a brief"}


@pytest.mark.asyncio
async def test_every_role_reads_skills_and_a_stranger_does_not(world) -> None:
    for role in ("viewer", "member", "admin", "owner"):
        async with world.as_(role) as http:
            response = await http.get("/?workspace_id=ws-1")
            assert response.status_code == 200, role
            assert "shared" in {s["id"] for s in response.json()}
            assert (await http.get("/shared")).status_code == 200
    async with world.as_("stranger") as http:
        assert (await http.get("/?workspace_id=ws-1")).status_code == 403
        assert (await http.get("/shared")).status_code == 403


@pytest.mark.asyncio
async def test_a_private_skill_is_its_creators_alone(world) -> None:
    async with world.as_("member") as http:
        assert (await http.get("/mine")).status_code == 200
    async with world.as_("admin") as http:
        assert "mine" not in {s["id"] for s in (await http.get("/?workspace_id=ws-1")).json()}
        assert (await http.get("/mine")).status_code == 403
        assert (await http.patch("/mine", json={"name": "x"})).status_code == 403
        assert (await http.delete("/mine")).status_code == 403
        assert (await http.post("/mine/use")).status_code == 403
    assert "mine" in world.store.records


@pytest.mark.asyncio
async def test_a_viewer_cannot_change_skills(world) -> None:
    async with world.as_("viewer") as http:
        assert (await http.post("/", json=NEW)).status_code == 403
        assert (await http.patch("/shared", json={"name": "x"})).status_code == 403
        assert (await http.post("/shared/use")).status_code == 403
        assert (await http.delete("/shared")).status_code == 403
    assert world.store.records["shared"].name == "shared"
    assert world.store.records["shared"].last_used_at is None


@pytest.mark.asyncio
async def test_a_member_writes_skills_and_a_stranger_cannot(world) -> None:
    async with world.as_("member") as http:
        assert (await http.post("/", json=NEW)).status_code == 200
        assert (await http.patch("/shared", json={"name": "Renamed"})).json()["name"] == "Renamed"
        assert (await http.post("/shared/use")).json()["last_used_at"] is not None
        assert (await http.delete("/shared")).json() == {"status": "deleted"}
    async with world.as_("stranger") as http:
        assert (await http.post("/", json=NEW)).status_code == 403


@pytest.mark.asyncio
async def test_a_skill_of_another_workspace_is_out_of_reach(world) -> None:
    async with world.as_("owner") as http:
        assert (await http.get("/other-ws")).status_code == 403
        assert (await http.patch("/other-ws", json={"name": "x"})).status_code == 403
        assert (await http.delete("/other-ws")).status_code == 403
    assert "other-ws" in world.store.records


@pytest.mark.asyncio
async def test_a_skill_that_does_not_exist_is_not_found(world) -> None:
    async with world.as_("member") as http:
        assert (await http.get("/nope")).status_code == 404
        assert (await http.delete("/nope")).status_code == 404


@pytest.mark.asyncio
async def test_the_skills_feature_gates_the_section() -> None:
    from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
    from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

    flags = FeatureFlagsConfig(
        enabled_features=["chat", "files"],
        role_baseline={"member": ["chat"], "owner": ["chat", "files"]},
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("member", "member", scope)
    app = FastAPI()
    app.include_router(adapter.router)
    app.dependency_overrides[adapter.get_skill_service] = lambda: SkillService(MemorySkills())
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="member")
    with nexus.installed():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
            denied = await http.get("/?workspace_id=ws-1")
    assert denied.status_code == 403
    assert "not available" in denied.json()["detail"]
