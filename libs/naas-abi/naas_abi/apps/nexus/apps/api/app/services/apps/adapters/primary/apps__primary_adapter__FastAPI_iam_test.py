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
    AppConfigCreateInput,
    AppConfigRecord,
    AppPersistencePort,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import access
from naas_abi.apps.nexus.apps.api.app.services.apps.service import AppsService
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
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
    monkeypatch.setattr(adapter, "_workspace_catalog_seed", no_slug)
    monkeypatch.setattr(adapter, "_remote_apps_catalog", no_remote)

    async def enabled_in_the_workspace(user_id, app_id, workspace_id):
        return workspace_id

    # Which workspace enables the app is the database's (access.py): the workspace asked for.
    monkeypatch.setattr(access, "remote_app_workspace", enabled_in_the_workspace)
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

    return nexus, as_, store, scope


@pytest.fixture
def world(monkeypatch):
    # Every role holds the apps section, so only the action's level decides.
    flags = FeatureFlagsConfig(
        enabled_features=["apps", "chat"],
        role_baseline={role: ["apps", "chat"] for role in ("owner", "admin", "member", "viewer")},
    )
    nexus, as_, store, scope = _world(flags, monkeypatch)
    # Links are grants IAM stores: the same IAM makes them.
    previous = credentials.configure_iam(lambda: nexus.iam)
    try:
        with nexus.installed():
            yield SimpleNamespace(as_=as_, store=store, iam=nexus, scope=scope)
    finally:
        credentials.configure_iam(previous)


@pytest.mark.asyncio
async def test_admins_list_every_app_viewers_and_members_none_and_a_stranger_nothing(
    world,
) -> None:
    for role in ("viewer", "member", "admin", "owner"):
        async with world.as_(role) as http:
            listed = await http.get("/api/apps/?workspace_id=ws-1")
            assert listed.status_code == 200, role
            expected = [APP] if role in ("admin", "owner") else []
            assert [a["app_id"] for a in listed.json()["apps"]] == expected, role
            assert (await http.get("/api/apps/ws-1")).status_code == 200
            assert (await http.get(f"/api/apps/ws-1/{APP}")).status_code == 404  # no row yet
    async with world.as_("stranger") as http:
        assert (await http.get("/api/apps/?workspace_id=ws-1")).status_code == 403
        assert (await http.get("/api/apps/ws-1")).status_code == 403
        assert (await http.get(f"/api/apps/ws-1/{APP}")).status_code == 403
    async with world.as_("admin") as http:
        assert (await http.get("/api/apps/?workspace_id=ws-2")).status_code == 403


@pytest.mark.asyncio
async def test_a_grant_of_one_app_lists_and_opens_that_app_alone(world, monkeypatch) -> None:
    catalog = adapter._scan_apps_catalog()
    other = adapter._build_app_info("acme.ops", Path("/modules/chart"), {"name": "Chart"})
    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: (*catalog, other))
    world.iam.allow_scope("member", ModuleScope("app", "acme.ops", "map"), world.scope)
    for app_id in (APP, "acme.ops:chart"):
        await world.store.create(
            AppConfigCreateInput(workspace_id="ws-1", app_id=app_id, enabled=True)
        )
    link = {"workspace_id": "ws-1", "path_prefix": "/app-html/acme/ops/map/"}
    async with world.as_("member") as http:
        listed = await http.get("/api/apps/?workspace_id=ws-1")
        assert [a["app_id"] for a in listed.json()["apps"]] == [APP]
        assert [c["app_id"] for c in (await http.get("/api/apps/ws-1")).json()] == [APP]
        assert (await http.get(f"/api/apps/ws-1/{APP}")).status_code == 200
        assert (await http.get("/api/apps/ws-1/acme.ops:chart")).status_code == 404
        assert (await http.post("/api/apps/access-token", json=link)).status_code == 200
        chart = {**link, "path_prefix": "/app-html/acme/ops/chart/"}
        assert (await http.post("/api/apps/access-token", json=chart)).status_code == 403
        # Not in another workspace.
        listed = await http.get("/api/apps/?workspace_id=ws-2")
        assert listed.status_code == 403


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
async def test_links_to_an_app_are_minted_for_those_who_may_open_it(world) -> None:
    link = {"workspace_id": "ws-1", "path_prefix": "/app-html/acme/ops/map/"}
    remote = {"workspace_id": "ws-1", "module_id": "acme.research", "app": "console"}
    for role in ("viewer", "member"):
        async with world.as_(role) as http:
            assert (await http.post("/api/apps/access-token", json=link)).status_code == 403, role
            assert (await http.post("/api/apps/remote-grant", json=remote)).status_code == 403, role
        world.iam.allow_scope(role, ModuleScope("app", "acme.ops", "map"), world.scope)
        world.iam.allow_scope(role, ModuleScope("app", "acme.research", "console"), world.scope)
    for role in ("viewer", "member", "admin"):
        async with world.as_(role) as http:
            assert (await http.post("/api/apps/access-token", json=link)).status_code == 200, role
            assert (await http.post("/api/apps/remote-grant", json=remote)).status_code == 200, role
    async with world.as_("admin") as http:
        # A link opens one app: a lock naming none, or no lock, is refused.
        for prefix in (None, "/app-html/", "/app-html/acme/ops/other/"):
            unlocked = {**link, "path_prefix": prefix}
            assert (await http.post("/api/apps/access-token", json=unlocked)).status_code == 400
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


@pytest.mark.asyncio
async def test_an_app_of_a_dotted_module_path_opens_by_its_id_or_its_folder(
    world, monkeypatch
) -> None:
    """``naas_abi_marketplace.domains.personnel:cockpit`` is served from
    ``/app-html/naas_abi_marketplace/domains/personnel/cockpit/``: the link is
    locked to that folder, whether the client names the app or the folder."""
    module = "naas_abi_marketplace.domains.personnel"
    cockpit = adapter._build_app_info(module, Path("/modules/cockpit"), {"name": "Cockpit"})
    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: (cockpit,))
    folder = "/app-html/naas_abi_marketplace/domains/personnel/cockpit/"
    async with world.as_("admin") as http:
        by_id = await http.post(
            "/api/apps/access-token", json={"workspace_id": "ws-1", "app_id": cockpit.app_id}
        )
        assert by_id.status_code == 200, by_id.text
        assert by_id.json()["path_prefix"] == folder
        by_folder = await http.post(
            "/api/apps/access-token", json={"workspace_id": "ws-1", "path_prefix": folder}
        )
        assert by_folder.json()["path_prefix"] == folder
        # The two-segment prefix an old client sent names no app.
        truncated = {
            "workspace_id": "ws-1",
            "path_prefix": "/app-html/naas_abi_marketplace/domains/",
        }
        assert (await http.post("/api/apps/access-token", json=truncated)).status_code == 400
        # An app_id and a lock that is not its folder disagree.
        both = {"workspace_id": "ws-1", "app_id": cockpit.app_id, "path_prefix": "/app-html/x/"}
        assert (await http.post("/api/apps/access-token", json=both)).status_code == 400
        unknown = {"workspace_id": "ws-1", "app_id": "acme.ops:nothing"}
        assert (await http.post("/api/apps/access-token", json=unknown)).status_code == 400
    async with world.as_("member") as http:
        refused = {"workspace_id": "ws-1", "app_id": cockpit.app_id}
        assert (await http.post("/api/apps/access-token", json=refused)).status_code == 403
    world.iam.allow_scope("member", ModuleScope("app", module, "cockpit"), world.scope)
    async with world.as_("member") as http:
        allowed = {"workspace_id": "ws-1", "app_id": cockpit.app_id}
        assert (await http.post("/api/apps/access-token", json=allowed)).status_code == 200


def test_a_path_lock_names_the_catalog_app_it_covers(monkeypatch) -> None:
    catalog = (adapter._build_app_info("acme.ops", Path("/modules/map"), {"name": "Map"}),)
    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: catalog)

    assert adapter._app_id_of_prefix("/app-html/acme/ops/map/") == APP
    assert adapter._app_id_of_prefix("/app-html/acme/ops/map") == APP
    assert adapter._app_id_of_prefix("/app-html/acme/ops/other/") == "-"
    assert adapter._app_id_of_prefix(None) == "-"


@pytest.mark.asyncio
async def test_the_apps_section_does_not_gate_opening_an_app(monkeypatch) -> None:
    # The deployment defaults: members hold no "apps" section, which is the
    # settings page. The app's module scope alone decides who opens it.
    nexus, as_, _, scope = _world(None, monkeypatch)
    with nexus.installed():
        nexus.allow_scope("member", ModuleScope("app", "acme.ops", "map"), scope)
        async with as_("member") as http:
            listed = await http.get("/api/apps/?workspace_id=ws-1")
            assert [a["app_id"] for a in listed.json()["apps"]] == [APP]
            denied = await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": True})
            assert denied.status_code == 403


# -- the workspace's set and what it turned off ------------------------------------------


@pytest.fixture
def shown(world):
    """Apps on and off as the store says (``app_configs.enabled``, else off)."""
    from naas_abi.apps.nexus.apps.api.app.services.apps.visibility import AppsVisibility
    from naas_abi.apps.nexus.apps.api.app.services.visibility.testing import (
        visibility_installed,
    )

    async def states(workspace_id):
        return await AppsService(world.store).get_enabled_states(workspace_id)

    async def no_seed(workspace_id):
        return set()

    with visibility_installed({"app": AppsVisibility(states, no_seed)}):
        yield world


@pytest.mark.asyncio
async def test_a_workspace_lists_only_the_apps_of_its_set(world, monkeypatch) -> None:
    catalog = adapter._scan_apps_catalog()
    other = adapter._build_app_info("acme.market", Path("/modules/prices"), {"name": "Prices"})
    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: (*catalog, other))
    world.iam.platform_admin("root")
    world.iam.put_set("org-1", "ws-1", modules=["acme.market"])
    for role in ("admin", "owner", "root"):
        async with world.as_(role) as http:
            listed = await http.get("/api/apps/?workspace_id=ws-1")
            assert [a["app_id"] for a in listed.json()["apps"]] == ["acme.market:prices"], role
    # One app of a module, not the module.
    world.iam.put_set("org-1", "ws-1", modules=["app/acme.ops/map"])
    async with world.as_("root") as http:
        listed = await http.get("/api/apps/?workspace_id=ws-1")
        assert [a["app_id"] for a in listed.json()["apps"]] == [APP]


@pytest.mark.asyncio
async def test_nothing_outside_the_set_is_turned_on_from_workspace_settings(world) -> None:
    world.iam.put_set("org-1", "ws-1", modules=["acme.market"])
    async with world.as_("admin") as http:
        refused = await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": True})
        assert refused.status_code == 403
        assert "not in the workspace's set" in refused.json()["detail"]
        assert (await http.post("/api/apps/ws-1", json={"app_id": APP})).status_code == 403
        # Turning one off is always allowed.
        off = await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": False})
        assert off.status_code == 200
    assert world.store.rows[("ws-1", APP)].enabled is False


@pytest.mark.asyncio
async def test_an_app_turned_off_is_refused_to_everyone_and_listed_to_its_admins(shown) -> None:
    link = {"workspace_id": "ws-1", "app_id": APP}
    remote = {"workspace_id": "ws-1", "module_id": "acme.ops", "app": "map"}
    shown.iam.allow_scope("member", ModuleScope("app", "acme.ops", "map"), shown.scope)
    shown.iam.platform_admin("root")
    async with shown.as_("admin") as http:
        assert (
            await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": True})
        ).status_code == 200
    async with shown.as_("member") as http:
        listed = await http.get("/api/apps/?workspace_id=ws-1")
        assert [a["app_id"] for a in listed.json()["apps"]] == [APP]
        assert (await http.post("/api/apps/access-token", json=link)).status_code == 200
    async with shown.as_("admin") as http:
        assert (
            await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": False})
        ).status_code == 200
    for who in ("member", "admin", "owner", "root"):
        async with shown.as_(who) as http:
            opened = await http.post("/api/apps/access-token", json=link)
            assert opened.status_code == 403, who
            assert opened.json()["detail"] == "This app is turned off in this workspace"
            assert (await http.post("/api/apps/remote-grant", json=remote)).status_code == 403
    async with shown.as_("member") as http:
        assert (await http.get("/api/apps/?workspace_id=ws-1")).json()["apps"] == []
        assert (await http.get("/api/apps/ws-1")).json() == []
        assert (await http.get(f"/api/apps/ws-1/{APP}")).status_code == 404
    # Its admins still list it, off, to turn it back on.
    async with shown.as_("admin") as http:
        listed = (await http.get("/api/apps/?workspace_id=ws-1")).json()["apps"]
        assert [(a["app_id"], a["enabled"]) for a in listed] == [(APP, False)]
        assert (await http.get(f"/api/apps/ws-1/{APP}")).json()["enabled"] is False


@pytest.mark.asyncio
async def test_a_grant_to_switch_one_app_lists_that_app_while_it_is_off(shown) -> None:
    """Who may turn an app back on is asked on that app, as the toggle is: a member
    granted UpdateApp on it alone turns it off and still sees it to turn it on."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource

    shown.iam.allow_scope("member", ModuleScope("app", "acme.ops", "map"), shown.scope)
    app_resource = nexus_resource("app", org="o", workspace="w", id=APP).removeprefix("abi:o:w:")
    shown.iam.allow("member", ["nexus:UpdateApp"], [f"${{scope}}:{app_resource}"], shown.scope)
    async with shown.as_("member") as http:
        assert (
            await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": False})
        ).status_code == 200
        listed = (await http.get("/api/apps/?workspace_id=ws-1")).json()["apps"]
        assert [(a["app_id"], a["enabled"]) for a in listed] == [(APP, False)]
        assert (await http.get(f"/api/apps/ws-1/{APP}")).status_code == 200
        assert (
            await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": True})
        ).status_code == 200
    # Another member, with the app but not the right to switch it, sees nothing off.
    shown.iam.grant("other", "member", shown.scope)
    shown.iam.allow_scope("other", ModuleScope("app", "acme.ops", "map"), shown.scope)
    async with shown.as_("admin") as http:
        await http.patch(f"/api/apps/ws-1/{APP}", json={"enabled": False})
    async with shown.as_("other") as http:
        assert (await http.get("/api/apps/?workspace_id=ws-1")).json()["apps"] == []
