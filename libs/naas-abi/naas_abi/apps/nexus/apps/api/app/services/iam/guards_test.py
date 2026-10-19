"""``guard`` on a real FastAPI route: it decides before the body is read."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from pydantic import BaseModel


class Body(BaseModel):
    name: str


router = APIRouter()


@router.get(
    "/{workspace_id}/files/{drive}/{path:path}",
    dependencies=[guard("GetFile", id=("drive", "path"), feature="files")],
)
async def read_file(workspace_id: str, drive: str, path: str) -> dict[str, str]:
    return {"drive": drive, "path": path}


@router.put(
    "/{workspace_id}/files/{drive}/{path:path}",
    dependencies=[guard("PutFile", id=("drive", "path"))],
)
async def write_file(workspace_id: str, drive: str, path: str, body: Body) -> dict[str, str]:
    return {"ok": body.name}


@router.get("/{workspace_id}/agents", dependencies=[guard("ListOntologies", literal="-")])
async def list_agents(workspace_id: str) -> list[str]:
    return []


@router.get("/search", dependencies=[guard("ListWorkspaces", workspace=None, org="org_id")])
async def by_org(org_id: str) -> str:
    return org_id


@router.post("/inline", dependencies=[declares("CreateConversation")])
async def inline() -> str:
    return "inline"


@pytest.fixture
def client(team):
    app = FastAPI()
    app.include_router(router)
    user = {"id": "member"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(**user)

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return as_


@pytest.mark.asyncio
async def test_roles_decide_before_the_body_is_validated(client) -> None:
    async with client("viewer") as http:
        assert (await http.get("/ws-1/files/workspace/a/b.txt")).json() == {
            "drive": "workspace",
            "path": "a/b.txt",
        }
        # A viewer's write is refused before the (invalid) body is looked at.
        assert (await http.put("/ws-1/files/workspace/a.txt", json={})).status_code == 403
    async with client("member") as http:
        assert (await http.put("/ws-1/files/workspace/a.txt", json={})).status_code == 422
        assert (
            await http.put("/ws-1/files/workspace/a.txt", json={"name": "n"})
        ).status_code == 200
    async with client("stranger") as http:
        denied = await http.get("/ws-1/files/workspace/a.txt")
        assert denied.status_code == 403
        assert "access to this workspace" in denied.json()["detail"]


@pytest.mark.asyncio
async def test_a_feature_the_role_lacks_is_refused(client) -> None:
    async with client("member") as http:
        assert (await http.get("/ws-1/agents")).status_code == 403  # members have no "ontology"
    async with client("admin") as http:
        assert (await http.get("/ws-1/agents")).status_code == 200


@pytest.mark.asyncio
async def test_org_level_guards_and_declared_routes(client) -> None:
    async with client("member") as http:
        assert (await http.get("/search?org_id=org-1")).status_code == 200
        assert (await http.get("/search?org_id=org-9")).status_code == 403
        assert (await http.post("/inline")).status_code == 200  # declares only: no check
