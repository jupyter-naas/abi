"""Who lists, opens and links apps: IAM decides alone, on the real router."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
    apps__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import access
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.names import PLATFORM

APP = "acme.ops:map"


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

    async def no_remote():
        return ()

    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: catalog)
    monkeypatch.setattr(adapter, "_remote_apps_catalog", no_remote)

    async def the_named_workspace(user_id, app_id, workspace_id):
        return workspace_id

    # The workspace a remote app opens in reads the database (access.py): the one asked for.
    monkeypatch.setattr(access, "remote_app_workspace", the_named_workspace)
    app = FastAPI()
    app.include_router(adapter.router, prefix="/api/apps")
    user = {"id": "member"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=user["id"], email=f"{user['id']}@example.com"
    )

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return nexus, as_, scope


@pytest.fixture
def world(monkeypatch):
    # Every role holds the apps section, so only the action's level decides.
    flags = FeatureFlagsConfig(
        enabled_features=["apps", "chat"],
        role_baseline={role: ["apps", "chat"] for role in ("owner", "admin", "member", "viewer")},
    )
    nexus, as_, scope = _world(flags, monkeypatch)
    # Links are grants IAM stores: the same IAM makes them.
    previous = credentials.configure_iam(lambda: nexus.iam)
    try:
        with nexus.installed():
            yield SimpleNamespace(as_=as_, iam=nexus, scope=scope)
    finally:
        credentials.configure_iam(previous)


@pytest.mark.asyncio
async def test_who_holds_the_app_lists_it_and_a_stranger_nothing(world) -> None:
    world.iam.allow_scope("admin", ModuleScope("app", "acme.ops", "map"), world.scope)
    for role in ("viewer", "member", "admin", "owner"):
        async with world.as_(role) as http:
            listed = await http.get("/api/apps/?workspace_id=ws-1")
            assert listed.status_code == 200, role
            expected = [APP] if role == "admin" else []
            assert [a["app_id"] for a in listed.json()["apps"]] == expected, role
            # No on/off: the listing carries no workspace state.
            assert all("enabled" not in a for a in listed.json()["apps"]), role
    async with world.as_("stranger") as http:
        assert (await http.get("/api/apps/?workspace_id=ws-1")).status_code == 403
    async with world.as_("admin") as http:
        assert (await http.get("/api/apps/?workspace_id=ws-2")).status_code == 403


@pytest.mark.asyncio
async def test_a_grant_of_one_app_lists_and_opens_that_app_alone(world, monkeypatch) -> None:
    catalog = adapter._scan_apps_catalog()
    other = adapter._build_app_info("acme.ops", Path("/modules/chart"), {"name": "Chart"})
    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: (*catalog, other))
    world.iam.allow_scope("member", ModuleScope("app", "acme.ops", "map"), world.scope)
    link = {"workspace_id": "ws-1", "path_prefix": "/app-html/acme/ops/map/"}
    async with world.as_("member") as http:
        listed = await http.get("/api/apps/?workspace_id=ws-1")
        assert [a["app_id"] for a in listed.json()["apps"]] == [APP]
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
async def test_the_per_workspace_app_switch_is_gone(world) -> None:
    async with world.as_("admin") as http:
        assert (await http.get("/api/apps/ws-1")).status_code in (404, 405)
        assert (await http.post("/api/apps/ws-1", json={"app_id": APP})).status_code in (404, 405)
        for method in ("get", "patch", "delete"):
            kwargs = {"json": {"enabled": True}} if method == "patch" else {}
            answered = await getattr(http, method)(f"/api/apps/ws-1/{APP}", **kwargs)
            assert answered.status_code in (404, 405), method


@pytest.mark.asyncio
async def test_links_to_an_app_are_minted_for_those_who_may_open_it(world) -> None:
    link = {"workspace_id": "ws-1", "path_prefix": "/app-html/acme/ops/map/"}
    remote = {"workspace_id": "ws-1", "module_id": "acme.research", "app": "console"}
    for role in ("viewer", "member", "admin"):
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
    async with world.as_("admin") as http:
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
    world.iam.allow_scope("admin", ModuleScope("app", module, "cockpit"), world.scope)
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
    nexus, as_, scope = _world(None, monkeypatch)
    with nexus.installed():
        nexus.allow_scope("member", ModuleScope("app", "acme.ops", "map"), scope)
        async with as_("member") as http:
            listed = await http.get("/api/apps/?workspace_id=ws-1")
            assert [a["app_id"] for a in listed.json()["apps"]] == [APP]


# -- IAM alone: no set, no workspace switch --------------------------------------------


@pytest.mark.asyncio
async def test_the_listing_is_exactly_what_iam_allows(world, monkeypatch) -> None:
    """Every app of every module is listed to whom a policy allows it, and an app
    a policy denies is gone from the listing and refused, for every role."""
    catalog = adapter._scan_apps_catalog()
    other = adapter._build_app_info("acme.market", Path("/modules/prices"), {"name": "Prices"})
    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: (*catalog, other))
    world.iam.allow_scope("member", ModuleScope("app", "acme.market", "prices"), world.scope)
    async with world.as_("member") as http:
        listed = await http.get("/api/apps/?workspace_id=ws-1")
        assert [a["app_id"] for a in listed.json()["apps"]] == ["acme.market:prices"]
    # Admins and owners granted every app of the module.
    for role in ("admin", "owner"):
        world.iam.allow(role, ["module:OpenApp"], ["${scope}/module:app/*"], world.scope)
    # A Deny in a policy is how a workspace stops offering an app.
    map_resource = ModuleScope("app", "acme.ops", "map").resource(PLATFORM).removeprefix(PLATFORM)
    with as_service_account("engine"):
        deny = world.iam.iam.create_policy(
            "no-map",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Deny",
                        "actions": ["module:OpenApp"],
                        "resources": [f"${{scope}}/{map_resource}"],
                    }
                ],
            },
        )
        for role in ("admin", "owner"):
            world.iam.iam.attach_policy(deny.id, world.iam.principal(role), world.scope)
    for role in ("admin", "owner"):
        async with world.as_(role) as http:
            listed = await http.get("/api/apps/?workspace_id=ws-1")
            assert APP not in [a["app_id"] for a in listed.json()["apps"]], role
            link = {"workspace_id": "ws-1", "app_id": APP}
            assert (await http.post("/api/apps/access-token", json=link)).status_code == 403


@pytest.mark.asyncio
async def test_an_admin_or_owner_with_no_policy_lists_and_opens_no_app(world) -> None:
    """Nothing but a policy lists an app: an admin or owner of the workspace
    holding no module scope there sees none and opens none."""
    link = {"workspace_id": "ws-1", "app_id": APP}
    remote = {"workspace_id": "ws-1", "module_id": "acme.ops", "app": "map"}
    for role in ("member", "admin", "owner"):
        async with world.as_(role) as http:
            assert (await http.get("/api/apps/?workspace_id=ws-1")).json()["apps"] == [], role
            assert (await http.post("/api/apps/access-token", json=link)).status_code == 403
            assert (await http.post("/api/apps/remote-grant", json=remote)).status_code == 403
