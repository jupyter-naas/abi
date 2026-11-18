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
from naas_abi.apps.nexus.apps.api.app.services.apps.pages_sso import verify_pages_sso_token
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


@pytest.mark.asyncio
async def test_open_app_mints_sso_for_that_person_and_that_app_only(world, monkeypatch) -> None:
    """OpenApp on one catalog app mints a proof for the signed-in email and that host.

    The body cannot name another person. A grant on this app does not mint a
    proof for a different app. A dev origin is an audience only while Nexus is
    local and ``NEXUS_DEV_APP_URLS`` names it. The map has no built-in entry.
    """
    portal = adapter._build_app_info(
        "acme.portal",
        Path("/modules/site"),
        {"name": "Site", "url": "https://portal.example.com"},
    )
    other = adapter._build_app_info(
        "acme.portal",
        Path("/modules/other"),
        {"name": "Other", "url": "https://other.example.com"},
    )
    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: (portal, other))
    live = {"nexus_env": "local"}
    monkeypatch.setattr(
        adapter,
        "_live_settings",
        lambda: SimpleNamespace(
            pages_sso_secret="sso-test-secret",
            pages_sso_expire_seconds=60,
            nexus_env=live["nexus_env"],
        ),
    )
    monkeypatch.setenv("NEXUS_DEV_APP_URLS", "acme.portal:site=http://localhost:9")
    world.iam.allow_scope("member", ModuleScope("app", "acme.portal", "site"), world.scope)

    async def post(http, **extra):
        body = {"workspace_id": "ws-1", "audience": "localhost", "app_id": portal.app_id}
        body.update(extra)
        return await http.post("/api/apps/sso-token", json=body)

    async with world.as_("viewer") as http:
        assert (await post(http)).status_code == 403
    async with world.as_("member") as http:
        assert (await post(http, app_id=other.app_id)).status_code == 403
        assert (await post(http, audience="other.example.com")).status_code == 400
        minted = await post(http, email="someone-else@example.com")
        assert minted.status_code == 200, minted.text
        token = minted.json()["token"]
        assert (
            verify_pages_sso_token(token, secret="sso-test-secret", audience="localhost")
            == "member@example.com"
        )
        assert "someone-else@" not in token
        published = await post(http, audience="portal.example.com")
        assert published.status_code == 200
        live["nexus_env"] = "cloudflare"
        assert (await post(http)).status_code == 400
        assert (await post(http, audience="portal.example.com")).status_code == 200


def _sso_catalog(monkeypatch, **settings):
    """Two apps of one module, each a portal on its own host, and the live
    settings the SSO route reads (overridable per test)."""
    portal = adapter._build_app_info(
        "acme.portal", Path("/modules/site"), {"name": "Site", "url": "https://portal.example.com"}
    )
    other = adapter._build_app_info(
        "acme.portal", Path("/modules/other"), {"name": "Other", "url": "https://other.example.com"}
    )
    monkeypatch.setattr(adapter, "_scan_apps_catalog", lambda: (portal, other))
    live = SimpleNamespace(
        pages_sso_secret="sso-test-secret",
        pages_sso_expire_seconds=60,
        nexus_env="local",
        frontend_url="http://localhost:3042",
        nexus_dev_app_urls="",
    )
    for name, value in settings.items():
        setattr(live, name, value)
    monkeypatch.setattr(adapter, "_live_settings", lambda: live)
    return portal, other, live


def _deny(world, role: str, action: str, resource: str) -> None:
    with as_service_account("engine"):
        policy = world.iam.iam.create_policy(
            f"deny-{role}-{action}",
            {
                "version": "2026-10-13",
                "statements": [{"effect": "Deny", "actions": [action], "resources": [resource]}],
            },
        )
        world.iam.iam.attach_policy(policy.id, world.iam.principal(role), world.scope)


async def _sso(http, **body):
    return await http.post("/api/apps/sso-token", json={"workspace_id": "ws-1", **body})


@pytest.mark.asyncio
async def test_sso_without_app_id_asks_use_app_and_names_any_host(world, monkeypatch) -> None:
    """The route's older form: ``UseApp`` in the workspace, any hostname the
    portal will check. A Deny of ``UseApp`` refuses it; so does another workspace."""
    _sso_catalog(monkeypatch)
    async with world.as_("member") as http:
        minted = await _sso(http, audience="anything.example.org")
        assert minted.status_code == 200, minted.text
        token = minted.json()["token"]
        assert (
            verify_pages_sso_token(token, secret="sso-test-secret", audience="anything.example.org")
            == "member@example.com"
        )
        other_ws = await http.post(
            "/api/apps/sso-token", json={"workspace_id": "ws-2", "audience": "a.example.org"}
        )
        assert other_ws.status_code == 403
    async with world.as_("stranger") as http:
        assert (await _sso(http, audience="anything.example.org")).status_code == 403
    _deny(world, "member", "nexus:UseApp", "${scope}/*")
    async with world.as_("member") as http:
        assert (await _sso(http, audience="anything.example.org")).status_code == 403


@pytest.mark.asyncio
async def test_sso_names_an_app_of_the_catalog_the_caller_may_open(world, monkeypatch) -> None:
    """An id that is no app's is a 400 before IAM. IAM is asked before the
    catalog, so a missing app is told apart only for someone granted it. A
    remote app has no portal host (it opens at ``/app-html/remote/``): the web
    app never asks for it, and the route refuses it. A Deny wins over a grant."""
    portal, _, _ = _sso_catalog(monkeypatch)
    ghost = ModuleScope("app", "acme.portal", "ghost")
    remote = ModuleScope("app", "acme.research", "console")
    async with world.as_("member") as http:
        for bad in ("no-colon", ":site", "acme.portal:", "remote/:x"):
            answered = await _sso(http, audience="portal.example.com", app_id=bad)
            assert answered.status_code == 400, bad
        # Not granted: IAM refuses before the catalog is read.
        assert (
            await _sso(http, audience="portal.example.com", app_id="acme.portal:ghost")
        ).status_code == 403
    world.iam.allow_scope("member", ghost, world.scope)
    world.iam.allow_scope("member", remote, world.scope)
    world.iam.allow_scope("member", ModuleScope("app", "acme.portal", "site"), world.scope)
    async with world.as_("member") as http:
        missing = await _sso(http, audience="portal.example.com", app_id="acme.portal:ghost")
        assert missing.status_code == 400
        assert missing.json()["detail"] == "app_id names no app"
        answered = await _sso(
            http, audience="portal.example.com", app_id="remote/acme.research:console"
        )
        assert answered.status_code == 400
        assert (
            await _sso(http, audience="portal.example.com", app_id=portal.app_id)
        ).status_code == 200
    _deny(world, "member", "module:OpenApp", "${scope}/module:app/acme.portal/site")
    async with world.as_("member") as http:
        assert (
            await _sso(http, audience="portal.example.com", app_id=portal.app_id)
        ).status_code == 403


@pytest.mark.asyncio
async def test_sso_without_a_secret_is_off_for_those_allowed_only(world, monkeypatch) -> None:
    portal, _, _ = _sso_catalog(monkeypatch, pages_sso_secret="")
    world.iam.allow_scope("member", ModuleScope("app", "acme.portal", "site"), world.scope)
    async with world.as_("member") as http:
        assert (
            await _sso(http, audience="portal.example.com", app_id=portal.app_id)
        ).status_code == 503
        assert (await _sso(http, audience="anything.example.org")).status_code == 503
    async with world.as_("viewer") as http:
        assert (
            await _sso(http, audience="portal.example.com", app_id=portal.app_id)
        ).status_code == 403
