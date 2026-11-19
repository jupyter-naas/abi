"""An organization skill reaches every chat of the organization: it is the
organization's admins' to make, each workspace's admins' to turn off there, and a
chat carries only the skills its user may use. Real routes, PostgreSQL adapter (on
SQLite), IAM and chat prompt."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.skills import SkillCreateInput
from naas_abi.apps.nexus.apps.api.app.services.skills.adapters.primary import (
    skills__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.skills.adapters.secondary.postgres import (
    SkillSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.skills.port import MAX_PROMPT_CHARS
from naas_abi.apps.nexus.apps.api.app.services.skills.service import (
    SkillService,
    SkillValidationError,
)

PROMPT = "Answer in three bullet points."


@pytest_asyncio.fixture
async def world(nexus_db):
    async with nexus_db() as db:
        db.add(UserModel(id="owner", email="owner@example.com", name="Owner"))
        db.add(OrganizationModel(id="org-1", name="Org", slug="org", owner_id="owner"))
        for ws in ("ws-1", "ws-2"):
            db.add(
                WorkspaceModel(id=ws, name=ws, slug=ws, owner_id="owner", organization_id="org-1")
            )
        await db.commit()
    session = nexus_db()
    service = SkillService(SkillSecondaryAdapterPostgres(db=session))
    flags = FeatureFlagsConfig(
        role_baseline={
            "member": ["chat", "skills"],
            "admin": ["chat", "skills"],
            "owner": ["chat", "skills"],
            "viewer": ["chat"],
        }
    )
    nexus = NexusIam(flags)
    org = nexus.org("org-1")
    ws1, ws2 = nexus.workspace("org-1", "ws-1"), nexus.workspace("org-1", "ws-2")
    nexus.grant("member1", "member", ws1)
    nexus.grant("orgadmin", "admin", org)
    nexus.grant("member2", "member", ws2)
    nexus.grant("admin2", "admin", ws2)
    nexus.grant("viewer2", "viewer", ws2)

    app = FastAPI()
    app.include_router(adapter.router)
    app.dependency_overrides[adapter.get_skill_service] = lambda: service
    who = {"id": "member1"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id=who["id"])

    def as_(user_id: str) -> AsyncClient:
        who["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    async def block(user_id: str, workspace_id: str) -> str:
        chat = ChatService(adapter=SimpleNamespace(), skills_service=service)
        return await chat._build_skills_block(user_id, workspace_id)

    with nexus.installed():
        yield SimpleNamespace(as_=as_, block=block, service=service, nexus=nexus)
    await session.close()


def _new(scope: str, workspace: str = "ws-1", prompt: str = PROMPT) -> dict:
    return {"workspace_id": workspace, "name": "Brief", "scope": scope, "prompt": prompt}


async def _org_skill(world) -> str:
    async with world.as_("orgadmin") as http:
        made = await http.post("/", json={**_new("organization"), "name": "Org brief"})
    assert made.status_code == 200, made.text
    return made.json()["id"]


@pytest.mark.asyncio
async def test_an_organization_skill_keeps_to_the_organizations_admins(world) -> None:
    async with world.as_("member1") as http:
        assert (await http.post("/", json=_new("organization"))).status_code == 403
        own = await http.post("/", json=_new("workspace"))
        assert own.status_code == 200, own.text
        widened = await http.patch(f"/{own.json()['id']}", json={"scope": "organization"})
        assert widened.status_code == 403
    sid = await _org_skill(world)
    async with world.as_("member1") as http:
        assert (await http.patch(f"/{sid}", json={"prompt": "Other"})).status_code == 403
    async with world.as_("member2") as http:
        listed = await http.get("/?workspace_id=ws-2")
    assert [s["id"] for s in listed.json()] == [sid]
    assert PROMPT in await world.block("member2", "ws-2")


@pytest.mark.asyncio
async def test_a_workspace_keeps_an_organization_skill_out_of_its_chats(world) -> None:
    sid = await _org_skill(world)
    async with world.as_("member2") as http:
        refused = await http.put(f"/{sid}/workspaces/ws-2", json={"enabled": False})
    assert refused.status_code == 403
    async with world.as_("admin2") as http:
        off = await http.put(f"/{sid}/workspaces/ws-2", json={"enabled": False})
    assert off.status_code == 200, off.text
    assert off.json()["enabled_here"] is False
    assert PROMPT not in await world.block("member2", "ws-2")
    # Only there: the organization's other workspaces still carry it.
    assert PROMPT in await world.block("member1", "ws-1")
    async with world.as_("admin2") as http:
        on = await http.put(f"/{sid}/workspaces/ws-2", json={"enabled": True})
    assert on.json()["enabled_here"] is True
    assert PROMPT in await world.block("member2", "ws-2")


@pytest.mark.asyncio
async def test_the_chat_keeps_the_skills_its_user_may_not_use_out(world) -> None:
    await _org_skill(world)
    # A viewer of ws-2 has no skills feature there.
    assert PROMPT not in await world.block("viewer2", "ws-2")
    assert PROMPT not in await world.block("stranger", "ws-2")
    assert PROMPT in await world.block("member2", "ws-2")


@pytest.mark.asyncio
async def test_a_switch_keeps_to_organization_skills(world) -> None:
    sid = await _org_skill(world)
    async with world.as_("orgadmin") as http:
        off = await http.put(f"/{sid}/workspaces/ws-1", json={"enabled": False})
        assert off.json()["enabled_here"] is False
        narrowed = await http.patch(f"/{sid}", json={"scope": "workspace"})
        assert narrowed.status_code == 200, narrowed.text
        listed = await http.get("/?workspace_id=ws-1")
    assert [(s["id"], s["enabled_here"]) for s in listed.json()] == [(sid, True)]
    assert PROMPT in await world.block("member1", "ws-1")


@pytest.mark.asyncio
async def test_an_organization_skill_without_its_organization_recorded_keeps_to_its_admins(
    world,
) -> None:
    from naas_abi.apps.nexus.apps.api.app.models import SkillModel

    # An organization skill recorded before its organization was copied onto it.
    session = world.service.adapter.db
    session.add(
        SkillModel(
            id="legacy",
            workspace_id="ws-1",
            organization_id=None,
            user_id="owner",
            name="Legacy",
            slug="legacy",
            prompt=PROMPT,
            scope="organization",
            enabled=True,
        )
    )
    await session.commit()
    async with world.as_("member1") as http:
        assert (await http.delete("/legacy")).status_code == 403
    async with world.as_("orgadmin") as http:
        assert (await http.delete("/legacy")).status_code == 200


@pytest.mark.asyncio
async def test_a_skill_prompt_keeps_to_its_length(world) -> None:
    long = "x" * (MAX_PROMPT_CHARS + 1)
    async with world.as_("member1") as http:
        assert (await http.post("/", json=_new("workspace", prompt=long))).status_code == 422
        made = await http.post("/", json=_new("workspace"))
        patched = await http.patch(f"/{made.json()['id']}", json={"prompt": long})
    assert patched.status_code == 422
    # The service refuses it too, for the callers that are not the route.
    with pytest.raises(SkillValidationError):
        await world.service.create_skill(
            SkillCreateInput(
                workspace_id="ws-1", user_id="member1", name="Long", slug="long", prompt=long
            )
        )
