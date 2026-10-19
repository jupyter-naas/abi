"""Who lists, opens, links and turns on apps: IAM decides, on the real router."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
    apps__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.port import (
    AppConfigRecord,
    AppPersistencePort,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.service import AppsService
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

APP = "acme.ops:map"


class MemoryApps(AppPersistencePort):
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], AppConfigRecord] = {}

    async def list_by_workspace(self, workspace_id):
        return [r for (ws, _), r in self.rows.items() if ws == workspace_id]

    async def get(self, workspace_id, app_id):
        return self.rows.get((workspace_id, app_id))

    async def create(self, data):
        now = datetime(2026, 10, 1)
        record = AppConfigRecord(
            f"{data.workspace_id}/{data.app_id}",
            data.workspace_id,
            data.app_id,
            data.enabled,
            now,
            now,
        )
        self.rows[(data.workspace_id, data.app_id)] = record
        return record

    async def update(self, workspace_id, app_id, updates):
        record = self.rows.get((workspace_id, app_id))
        if record is not None and updates.enabled is not None:
            record.enabled = updates.enabled
        return record

    async def delete(self, workspace_id, app_id):
        return self.rows.pop((workspace_id, app_id), None) is not None


def _world(flags: FeatureFlagsConfig | None, monkeypatch):
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.workspace("org-1", "ws-2")
    for user in ("owner", "admin", "member", "viewer"):
        nexus.grant(user, user, scope)
    nexus.user("stranger")

    catalog = (
        adapter._build_app_info("acme.ops", Path("/modules/map"), {"name": "Map"}).model_copy(
            update={"installed": True}
        ),
    )

    async def no_slug(workspace_id):
        return None

    async def no_remote():
        return ()

    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: catalog)
    monkeypatch.setattr(adapter, "_workspace_slug", no_slug)
    monkeypatch.setattr(adapter, "_remote_apps_catalog", no_remote)
    store = MemoryApps()
    app = FastAPI()
    app.include_router(adapter.router, prefix="/api/apps")
    app.dependency_overrides[adapter.get_apps_service] = lambda: AppsService(store)
    user = {"id": "member"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=user["id"], email=f"{user['id']}@example.com"
    )

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return nexus, as_, store


@pytest.fixture
def world(monkeypatch):
    # Every role holds the apps section, so only the action's level decides.
    flags = FeatureFlagsConfig(
        enabled_features=["apps", "chat"],
        role_baseline={role: ["apps", "chat"] for role in ("owner", "admin", "member", "viewer")},
    )
    nexus, as_, store = _world(flags, monkeypatch)
    # Links are grants IAM stores: the same IAM makes them.
    previous = credentials.configure_iam(lambda: nexus.iam)
    try:
        with nexus.installed():
            yield SimpleNamespace(as_=as_, store=store)
    finally:
        credentials.configure_iam(previous)


@pytest.mark.asyncio
async def test_every_role_lists_and_reads_apps_and_a_stranger_does_not(world) -> None:
    for role in ("viewer", "member", "admin", "owner"):
        async with world.as_(role) as http:
            listed = await http.get("/api/apps/?workspace_id=ws-1")
            assert listed.status_code == 200, role
            assert [a["app_id"] for a in listed.json()["apps"]] == [APP]
            assert (await http.get("/api/apps/ws-1")).status_code == 200
            assert (await http.get(f"/api/apps/ws-1/{APP}")).status_code == 404  # no row yet
    async with world.as_("stranger") as http:
        assert (await http.get("/api/apps/?workspace_id=ws-1")).status_code == 403
        assert (await http.get("/api/apps/ws-1")).status_code == 403
        assert (await http.get(f"/api/apps/ws-1/{APP}")).status_code == 403
    async with world.as_("admin") as http:
        assert (await http.get("/api/apps/?workspace_id=ws-2")).status_code == 403


@pytest.mark.asyncio
async def test_a_listing_names_its_workspace(world) -> None:
    async with world.as_("viewer") as http:
        assert (await http.get("/api/apps/")).status_code == 422


@pytest.mark.asyncio
async def test_turning_an_app_on_or_off_is_for_admins(world) -> None:
    for role in ("viewer", "member"):
        async with world.as_(role) as http:
            assert (await http.post("/api/apps/ws-1", json={"app_id": APP})).status_code == 403
            assert (
                await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": True})
            ).status_code == 403
            assert (await http.delete(f"/api/apps/ws-1/{APP}")).status_code == 403
    assert world.store.rows == {}
    async with world.as_("admin") as http:
        assert (await http.post("/api/apps/ws-1", json={"app_id": APP})).status_code == 201
        assert (await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": False})).json()[
            "enabled"
        ] is False
        assert (await http.delete(f"/api/apps/ws-1/{APP}")).json() == {"status": "deleted"}
    async with world.as_("stranger") as http:
        assert (await http.post("/api/apps/ws-1", json={"app_id": APP})).status_code == 403
    async with world.as_("owner") as http:
        assert (await http.post("/api/apps/ws-2", json={"app_id": APP})).status_code == 403


@pytest.mark.asyncio
async def test_links_to_an_app_are_minted_for_the_workspace_users_only(world) -> None:
    link = {"workspace_id": "ws-1", "path_prefix": "/app-html/acme/ops/map/"}
    remote = {"workspace_id": "ws-1", "module_id": "acme.research", "app": "console"}
    for role in ("viewer", "member", "admin"):
        async with world.as_(role) as http:
            assert (await http.post("/api/apps/access-token", json=link)).status_code == 200, role
            assert (await http.post("/api/apps/remote-grant", json=remote)).status_code == 200, role
    async with world.as_("stranger") as http:
        assert (await http.post("/api/apps/access-token", json=link)).status_code == 403
        assert (await http.post("/api/apps/remote-grant", json=remote)).status_code == 403
    async with world.as_("owner") as http:
        assert (
            await http.post("/api/apps/access-token", json={**link, "workspace_id": "ws-2"})
        ).status_code == 403
        assert (
            await http.post("/api/apps/remote-grant", json={**remote, "workspace_id": "ws-2"})
        ).status_code == 403
        # The workspace names the resource: a link request without one is invalid.
        assert (await http.post("/api/apps/access-token", json={})).status_code == 422


def test_a_path_lock_names_the_catalog_app_it_covers(monkeypatch) -> None:
    catalog = (adapter._build_app_info("acme.ops", Path("/modules/map"), {"name": "Map"}),)
    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: catalog)

    assert adapter._app_id_of_prefix("/app-html/acme/ops/map/") == APP
    assert adapter._app_id_of_prefix("/app-html/acme/ops/map") == APP
    assert adapter._app_id_of_prefix("/app-html/acme/ops/other/") == "-"
    assert adapter._app_id_of_prefix(None) == "-"


@pytest.mark.asyncio
async def test_the_apps_section_must_be_on_for_the_role(monkeypatch) -> None:
    # The deployment defaults: members hold no "apps" section.
    nexus, as_, _ = _world(None, monkeypatch)
    with nexus.installed():
        async with as_("member") as http:
            denied = await http.get("/api/apps/?workspace_id=ws-1")
            assert denied.status_code == 403
            assert "not available" in denied.json()["detail"]
        async with as_("admin") as http:
            assert (await http.get("/api/apps/?workspace_id=ws-1")).status_code == 200
