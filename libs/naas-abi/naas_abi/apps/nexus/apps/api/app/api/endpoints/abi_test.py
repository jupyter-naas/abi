"""ABI servers of a workspace: every role lists them, admins manage them."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints import abi
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

BASE = "/api/abi/workspaces"
NEW = {"name": "Prod", "endpoint": "https://abi.example.com", "api_key": "k-1"}


@pytest.fixture
def world(nexus_db):
    # Every role holds the settings section, so only the action's level decides.
    flags = FeatureFlagsConfig(
        enabled_features=["settings", "chat"],
        role_baseline={
            role: ["settings", "chat"] for role in ("owner", "admin", "member", "viewer")
        },
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.workspace("org-1", "ws-2")
    for user in ("owner", "admin", "member", "viewer"):
        nexus.grant(user, user, scope)
    nexus.user("stranger")

    async def db():
        async with nexus_db() as session:
            yield session

    app = FastAPI()
    app.include_router(abi.router, prefix="/api/abi")
    app.dependency_overrides[get_db] = db
    user = {"id": "admin"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(**user)

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    with nexus.installed():
        yield as_


@pytest.mark.asyncio
async def test_admins_manage_servers_and_nobody_below_them_does(world) -> None:
    async with world("admin") as http:
        created = await http.post(f"{BASE}/ws-1/abi-servers", json=NEW)
        assert created.status_code == 200
        server_id = created.json()["id"]
        assert "api_key" not in created.json()

    for role in ("viewer", "member"):
        async with world(role) as http:
            assert (
                await http.post(f"{BASE}/ws-1/abi-servers", json={**NEW, "name": "x"})
            ).status_code == 403
            url = f"{BASE}/ws-1/abi-servers/{server_id}"
            assert (await http.put(url, json={"enabled": False})).status_code == 403
            assert (await http.delete(url)).status_code == 403

    async with world("admin") as http:
        url = f"{BASE}/ws-1/abi-servers/{server_id}"
        assert (await http.put(url, json={"enabled": False})).json()["enabled"] is False
        assert (await http.delete(url)).json() == {"status": "deleted"}
        assert (await http.get(url)).status_code == 404


@pytest.mark.asyncio
async def test_every_role_reads_servers_and_a_stranger_does_not(world) -> None:
    async with world("owner") as http:
        server_id = (await http.post(f"{BASE}/ws-1/abi-servers", json=NEW)).json()["id"]
    for role in ("viewer", "member", "admin", "owner"):
        async with world(role) as http:
            assert len((await http.get(f"{BASE}/ws-1/abi-servers")).json()) == 1, role
            assert (await http.get(f"{BASE}/ws-1/abi-servers/{server_id}")).status_code == 200
    async with world("stranger") as http:
        assert (await http.get(f"{BASE}/ws-1/abi-servers")).status_code == 403
        assert (await http.post(f"{BASE}/ws-1/abi-servers", json=NEW)).status_code == 403
    async with world("owner") as http:
        assert (await http.get(f"{BASE}/ws-2/abi-servers")).status_code == 403
        # A server id of this workspace is not reachable through another one.
        assert (await http.get(f"{BASE}/ws-2/abi-servers/{server_id}")).status_code == 403
