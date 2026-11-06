"""A view on the server, end to end: real IAM, Nexus's migrations on SQLite, the identity
and guard middleware, the routes.

Cast: ``root`` (platform admin), ``olivia`` (admin of the organization Acme), ``carol``
(admin of Alpha), ``bob`` (owner of Alpha), ``dave`` (member of Alpha, with the feature
chat), ``eve`` (member of Bravo). Alpha and Bravo are Acme's workspaces.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from fastapi import APIRouter, FastAPI, Request
from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.models import (
    AuthSessionModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (  # noqa: E501
    router as auth_router,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    nexus_resource,
    org_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc import runtime as oidc_runtime
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.primary.oidc__primary_adapter__FastAPI import (  # noqa: E501
    router as oidc_router,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc.service import csrf_token
from naas_abi.apps.nexus.apps.api.app.services.settings_cache.middleware import (
    SettingsCacheMiddleware,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.sql_audit_log import (
    SqlAdminAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as import runtime as view_runtime
from naas_abi.apps.nexus.apps.api.app.services.view_as.adapters.primary.view_as__primary_adapter__ASGI import (  # noqa: E501
    ViewGuardMiddleware,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.adapters.primary.view_as__primary_adapter__FastAPI import (  # noqa: E501
    router as view_router,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.workspaces__primary_adapter__FastAPI import (  # noqa: E501
    router as workspaces_router,
)
from naas_abi_core.engine.call_context import as_service_account, current_call_context
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

API = "https://testserver"
NOW = datetime(2026, 11, 6, 10, 0, 0)
ORG, ALPHA, BRAVO = "acme", "alpha", "bravo"
LONG_AFTER = datetime(2100, 1, 1)


class FakeCache:
    """The cache the settings middleware reads, remembering what it is asked."""

    def __init__(self) -> None:
        self.stored: dict[str, dict] = {}
        self.reads: list[str] = []

    def get(self, key, ttl=None):
        from naas_abi_core.services.cache.CachePort import CacheNotFoundError

        self.reads.append(key)
        if key not in self.stored:
            raise CacheNotFoundError(key)
        return self.stored[key]

    def set_json(self, key, value) -> None:
        self.stored[key] = value

    def hot_available(self) -> bool:
        return False


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def _probe_router() -> APIRouter:
    router = APIRouter()

    def seen(request: Request) -> dict:
        context = current_call_context()
        container = context.container
        search = False
        if container:
            from naas_abi.apps.nexus.apps.api.app.services.iam import runtime as iam

            resource = nexus_resource("feature", container=container, id="search")
            search = iam.iam().authorize("nexus:UseFeature", resource).allowed
        return {
            "user": context.on_behalf_of.id if context.on_behalf_of else None,
            "groups": sorted(context.on_behalf_of.groups) if context.on_behalf_of else [],
            "container": container,
            "search": search,
            "viewer": getattr(request.state, "nexus_viewer", None)
            and request.state.nexus_viewer.id,
            "session_user": request.state.nexus_session.user_id
            if getattr(request.state, "nexus_session", None)
            else None,
        }

    @router.get("/probe/in-query")
    async def in_query(request: Request, workspace_id: str | None = None) -> dict:
        return seen(request)

    @router.get("/workspaces/{workspace_id}/probe")
    async def in_path(request: Request, workspace_id: str) -> dict:
        return seen(request)

    @router.get("/organizations/{org_id}/probe")
    async def org_page(request: Request, org_id: str) -> dict:
        return seen(request)

    @router.get("/admin/probe")
    async def platform_page(request: Request) -> dict:
        return seen(request)

    @router.get("/probe/names-nothing")
    async def names_nothing(request: Request) -> dict:
        return seen(request)

    for method in ("post", "put", "patch", "delete"):
        getattr(router, method)("/workspaces/{workspace_id}/probe")(in_path)
    return router


def _app(cache: FakeCache) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(oidc_router, prefix="/api/auth/oidc")
    app.include_router(workspaces_router, prefix="/api/workspaces")
    app.include_router(view_router, prefix="/api/iam/view-as")
    app.include_router(_probe_router(), prefix="/api")
    # What main.py does: the cache innermost, the guard in front of it, identity outermost.
    app.add_middleware(SettingsCacheMiddleware, cache_resolver=lambda: cache)
    app.add_middleware(ViewGuardMiddleware)
    app.add_middleware(RequestIdentityMiddleware)
    return app


class World:
    """The cast, their sessions, and a client per browser."""

    def __init__(self, nexus: NexusIam, sessions, app: FastAPI, clock: Clock, cache: FakeCache):
        self.nexus, self.sessions, self.app, self.clock, self.cache = (
            nexus,
            sessions,
            app,
            clock,
            cache,
        )
        self.principals: dict[str, str] = {}
        self.cookies: dict[str, str] = {}

    @property
    def iam(self):
        return self.nexus.iam

    async def person(self, user_id: str, name: str) -> str:
        principal = self.nexus.principal(user_id)
        self.principals[user_id] = principal
        async with self.sessions() as db:
            db.add(
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    name=name,
                    principal_id=principal,
                )
            )
            await db.commit()
        return principal

    async def sign_in(self, user_id: str, groups: tuple[str, ...] = (), at: datetime = NOW):
        """A browser session of the user (its row, as a sign-in leaves it): a client."""
        secret = f"secret-{user_id}-{len(self.cookies)}"
        self.cookies[f"{user_id}{len(self.cookies)}"] = secret
        async with self.sessions() as db:
            db.add(
                AuthSessionModel(
                    id=hashlib.sha256(secret.encode()).hexdigest(),
                    user_id=user_id,
                    principal_id=self.principals[user_id],
                    provider="idp",
                    group_ids=json.dumps(list(groups)),
                    refresh_at=LONG_AFTER,
                    expires_at=LONG_AFTER,
                    created_at=at,
                )
            )
            await db.commit()
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url=API,
            cookies={"nexus_session": secret},
            headers={"X-CSRF-Token": csrf_token(secret)},
        )
        client.session_secret = secret  # type: ignore[attr-defined]
        return client

    def audit_log(self) -> SqlAdminAuditLog:
        return SqlAdminAuditLog(lambda: database.async_engine, prefix="iam.")

    async def records(self, operation: str | None = None):
        entries = await self.audit_log().history(limit=100)
        return [e for e in entries if operation is None or e.operation == operation]


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    """Nexus's migrations on SQLite, run once: each test starts from a copy."""
    import asyncio
    import shutil

    path = tmp_path_factory.mktemp("migrated") / "nexus.db"

    async def migrate() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(database, "async_engine", engine)
            patch.setattr(database, "_is_sqlite", True)
            await database.init_db()
        await engine.dispose()

    asyncio.run(migrate())
    return lambda target: shutil.copy(path, target)


@pytest_asyncio.fixture
async def world(tmp_path, monkeypatch, migrated):
    migrated(tmp_path / "nexus.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    monkeypatch.setattr(database, "async_engine", engine)
    monkeypatch.setattr(database, "_is_sqlite", True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(settings, "api_url", API)
    monkeypatch.setattr(settings, "frontend_url", "https://web.test")

    nexus = NexusIam(features_with_roles=False)
    alpha = nexus.workspace(ORG, ALPHA)
    bravo = nexus.workspace(ORG, BRAVO)
    org = org_container(ORG)
    installed = nexus.installed()
    installed.__enter__()
    clock, cache = Clock(), FakeCache()
    previous_oidc = oidc_runtime.configure(
        oidc_runtime.OidcRuntime(lambda: None, lambda: nexus.iam)
    )
    oidc_runtime.RUNTIME.principals._cache_seconds = 0
    previous_view = view_runtime.configure(view_runtime.ViewAsRuntime(clock=clock))
    world = World(nexus, sessions, _app(cache), clock, cache)

    async with sessions() as db:
        db.add(UserModel(id="owner", email="owner@example.com", name="Owner"))
        await db.flush()
        db.add(OrganizationModel(id=ORG, name="Acme", slug="acme", owner_id="owner"))
        await db.flush()
        for ws_id, name in ((ALPHA, "Alpha"), (BRAVO, "Bravo")):
            db.add(
                WorkspaceModel(
                    id=ws_id, name=name, slug=ws_id, owner_id="owner", organization_id=ORG
                )
            )
        await db.commit()
    for user_id, name in (
        ("root", "Root"),
        ("olivia", "Olivia"),
        ("carol", "Carol"),
        ("bob", "Bob"),
        ("dave", "Dave"),
        ("eve", "Eve"),
    ):
        await world.person(user_id, name)
    nexus.platform_admin("root")
    nexus.grant("olivia", "admin", org)  # mirrored below the organization: every workspace
    nexus.grant("carol", "admin", alpha)
    nexus.grant("bob", "owner", alpha)
    nexus.grant("dave", "member", alpha)
    nexus.give_features(world.principals["dave"], ["chat"], alpha)
    nexus.grant("eve", "member", bravo)
    world.alpha, world.bravo = alpha, bravo
    try:
        yield world
    finally:
        view_runtime.configure(previous_view)
        oidc_runtime.configure(previous_oidc)
        installed.__exit__(None, None, None)
        await engine.dispose()


async def start(client, world, person: str, workspace: str = ALPHA):
    return await client.post(
        "/api/iam/view-as",
        json={"principal_id": world.principals[person], "workspace_id": workspace},
    )


@pytest.fixture
def root_browser(world):
    async def make():
        return await world.sign_in("root")

    return make


# -- Start ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_platform_admin_starts_a_view_as_carol_in_alpha(world) -> None:
    root = await world.sign_in("root")

    started = await start(root, world, "carol")

    assert started.status_code == 200, started.text
    assert started.json() == {
        "person": {"id": world.principals["carol"], "name": "Carol"},
        "workspace": {"id": ALPHA, "name": "Alpha"},
        "ends_at": "2026-11-06T10:15:00+00:00",
        "groups_from": None,  # Carol never signed in: stored groups only
    }
    session = (await root.get("/api/auth/oidc/session")).json()
    assert session["view"] == started.json()
    assert session["user"]["email"] == "root@example.com"  # still about the viewer


@pytest.mark.asyncio
async def test_groups_come_from_the_persons_most_recent_session(world) -> None:
    with as_service_account("engine"):
        group = world.iam.create_group("People")
    await world.sign_in("dave", groups=("grp_old",), at=NOW - timedelta(days=2))
    await world.sign_in("dave", groups=(group.id,), at=NOW - timedelta(hours=1))
    root = await world.sign_in("root")

    started = await start(root, world, "dave")

    assert started.status_code == 200, started.text
    assert started.json()["groups_from"] == "2026-11-06T09:00:00+00:00"
    probe = (await root.get(f"/api/probe/in-query?workspace_id={ALPHA}")).json()
    assert probe["groups"] == [group.id]


@pytest.mark.asyncio
async def test_iam_refuses_what_it_refuses_and_the_refusal_is_audited(world) -> None:
    carol = await world.sign_in("carol")

    owner = await start(carol, world, "bob")  # a workspace admin never views as its owner
    itself = await start(carol, world, "carol")
    nobody_in_bravo = await start(carol, world, "eve", BRAVO)

    assert owner.status_code == itself.status_code == nobody_in_bravo.status_code == 403
    assert "builtin.owner" in owner.json()["detail"]
    assert (await carol.get("/api/auth/oidc/session")).json()["view"] is None
    refused = await world.records("view_as_start")
    assert sorted(e.phase for e in refused) == ["failed"] * 3 + ["requested"] * 3
    assert {e.actor_id for e in refused} == {"carol"}


@pytest.mark.asyncio
async def test_nobody_views_as_the_platform_admin(world) -> None:
    await world.person("root2", "Root Two")
    world.nexus.platform_admin("root2")
    root = await world.sign_in("root")

    refused = await start(root, world, "root2")

    assert refused.status_code == 403 and "platform admin" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_an_admin_views_as_a_member_of_their_workspace(world) -> None:
    carol = await world.sign_in("carol")
    world.nexus.give_features(world.principals["carol"], ["chat"], world.alpha)

    started = await start(carol, world, "dave")

    assert started.status_code == 200, started.text
    assert started.json()["person"]["name"] == "Dave"


@pytest.mark.asyncio
async def test_the_workspaces_of_a_person_where_a_view_is_accepted(world) -> None:
    root, carol = await world.sign_in("root"), await world.sign_in("carol")

    def ask(client, person):
        return client.get(
            "/api/iam/view-as/workspaces",
            params={"principal_id": world.principals.get(person, person)},
        )

    as_root = await ask(root, "carol")
    assert as_root.json() == [
        {"id": ALPHA, "name": "Alpha", "organization": {"id": ORG, "name": "Acme"}}
    ]
    # Olivia is Acme's admin: every workspace of Acme, through the organization-wide role.
    assert [w["id"] for w in (await ask(root, "olivia")).json()] == [ALPHA, BRAVO]
    # Carol administers Alpha only: Eve is in Bravo.
    assert (await ask(carol, "eve")).json() == []
    assert (await ask(carol, "olivia")).json() == []  # Olivia holds more than Carol
    assert (await ask(root, "nobody-at-all")).json() == []


@pytest.mark.asyncio
async def test_a_view_is_started_from_a_browser_session_only(world) -> None:
    anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=world.app), base_url=API)

    assert (await start(anonymous, world, "carol")).status_code == 401
    assert (
        await anonymous.get("/api/iam/view-as/workspaces", params={"principal_id": "x"})
    ).status_code == 401


@pytest.mark.asyncio
async def test_a_second_session_of_the_viewer_has_a_view_of_its_own(world) -> None:
    first, second = await world.sign_in("root"), await world.sign_in("root")

    assert (await start(first, world, "carol")).status_code == 200
    assert (await second.get("/api/auth/oidc/session")).json()["view"] is None
    assert (await start(second, world, "dave")).status_code == 200
    assert (await first.get("/api/auth/me")).json()["name"] == "Carol"
    assert (await second.get("/api/auth/me")).json()["name"] == "Dave"


# -- During a view ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_during_a_view_the_request_is_the_persons_with_their_recorded_groups(world) -> None:
    with as_service_account("engine"):
        group = world.iam.create_group("Searchers")
    world.nexus.give_features(group.id, ["search"], world.alpha)
    await world.sign_in("dave", groups=(group.id,))
    root = await world.sign_in("root")
    before = (await root.get(f"/api/probe/in-query?workspace_id={ALPHA}")).json()
    assert before["user"] == "root"

    assert (await start(root, world, "dave")).status_code == 200

    me = (await root.get("/api/auth/me")).json()
    assert (me["id"], me["name"]) == ("dave", "Dave")
    probe = (await root.get(f"/api/probe/in-query?workspace_id={ALPHA}")).json()
    assert probe["user"] == "dave"  # on_behalf_of: AUTHZ.context and get_current_user agree
    assert probe["groups"] == [group.id]
    assert probe["container"] == world.alpha
    assert probe["viewer"] == "root" and probe["session_user"] == "root"
    # Decided as Dave through his group: the feature search is Dave's through it.
    assert probe["search"] is True
    # The session answer is still the viewer's (CSRF, /session).
    assert (await root.get("/api/auth/oidc/session")).json()["user"]["name"] == "Root"


@pytest.mark.asyncio
async def test_the_feature_flags_are_the_persons(world) -> None:
    root = await world.sign_in("root")
    assert (await start(root, world, "dave")).status_code == 200

    listed = (await root.get("/api/workspaces")).json()

    assert [w["id"] for w in listed] == [ALPHA]  # the viewed workspace only
    flags = listed[0]["feature_flags"]
    assert flags["chat"] is True and not any(v for k, v in flags.items() if k != "chat")
    assert listed[0]["current_user_role"] == "member"


@pytest.mark.asyncio
async def test_a_blank_workspace_beside_the_viewed_one_is_outside(world) -> None:
    root = await world.sign_in("root")
    assert (await start(root, world, "olivia")).status_code == 200

    for query in (
        f"workspace_id={ALPHA}&workspace_id=",
        f"workspace_id=&workspace_id={ALPHA}",
        "workspace_id=",
    ):
        refused = await root.get(f"/api/probe/in-query?{query}")
        assert refused.status_code == 403, query
        assert refused.json()["detail"].startswith("Outside this view"), query


@pytest.mark.asyncio
async def test_a_workspace_found_by_slug_is_the_viewed_one_only(world) -> None:
    root = await world.sign_in("root")
    assert (await start(root, world, "olivia")).status_code == 200  # Olivia reaches Bravo too

    assert (await root.get(f"/api/workspaces/slug/{ALPHA}")).status_code == 200
    assert (await root.get(f"/api/workspaces/slug/{BRAVO}")).status_code == 404


@pytest.mark.asyncio
async def test_a_bearer_credential_never_carries_a_view(world, monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import Credential
    from naas_abi.apps.nexus.apps.api.app.services.identity_events import middleware as mw

    root = await world.sign_in("root")
    assert (await start(root, world, "carol")).status_code == 200

    async def known(token: str):
        return Credential(kind="session", user_id="root")

    monkeypatch.setattr(mw, "bearer_credential", known)
    headers = {"Authorization": "Bearer token"}

    me = await root.get("/api/auth/me", headers=headers)
    assert me.json()["id"] == "root"
    # No view, so no read-only guard either: it is the viewer's own request.
    assert (await root.post(f"/api/workspaces/{ALPHA}/probe", headers=headers)).status_code == 200


# -- Confinement -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_the_viewed_workspace_is_answered(world) -> None:
    root = await world.sign_in("root")
    assert (await start(root, world, "olivia")).status_code == 200  # Alpha and Bravo are hers
    outside = "Outside this view: you are viewing as Olivia in Alpha"

    for path in (
        f"/api/probe/in-query?workspace_id={ALPHA}",
        f"/api/workspaces/{ALPHA}/probe",
    ):
        assert (await root.get(path)).status_code == 200, path
    for path in (
        f"/api/probe/in-query?workspace_id={BRAVO}",  # another workspace
        f"/api/workspaces/{BRAVO}/probe",
        f"/api/probe/in-query?workspace_id={ALPHA}&workspace_id={BRAVO}",
        "/api/probe/in-query",  # names none
        f"/api/organizations/{ORG}/probe",  # an organization page
        f"/api/organizations/{ORG}/probe?workspace_id={ALPHA}",  # a route that takes no workspace
        "/api/admin/probe",  # a platform page
        f"/api/probe/names-nothing?workspace_id={ALPHA}",
        "/api/iam/view-as/workspaces?principal_id=x",
        "/api/iam/admin/policies",
    ):
        refused = await root.get(path)
        assert (refused.status_code, refused.json()) == (403, {"detail": outside}), path


# -- Read-only -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_write_is_refused_but_stop_and_sign_out(world) -> None:
    root = await world.sign_in("root")
    assert (await start(root, world, "carol")).status_code == 200
    refusal = {"detail": "Read-only: you are viewing as Carol"}

    for method in ("POST", "PUT", "PATCH", "DELETE"):
        answer = await root.request(method, f"/api/workspaces/{ALPHA}/probe")
        assert (answer.status_code, answer.json()) == (403, refusal), method
    for path in ("/api/iam/view-as", "/api/settings-cache/refresh", "/api/workspaces"):
        answer = await root.post(path, json={})
        assert (answer.status_code, answer.json()) == (403, refusal), path
    # Not even a write of the viewer's own account: nothing in this browser acts as the viewer.
    assert (await root.patch("/api/auth/me", json={"name": "x"})).status_code == 403


@pytest.mark.asyncio
async def test_stop_is_allowed_during_a_view(world) -> None:
    root = await world.sign_in("root")
    assert (await start(root, world, "carol")).status_code == 200

    stopped = await root.delete("/api/iam/view-as")

    assert (stopped.status_code, stopped.json()) == (200, {"stopped": True})
    assert (await root.get("/api/auth/me")).json()["id"] == "root"
    assert (await root.get("/api/auth/oidc/session")).json()["view"] is None
    assert (await root.delete("/api/iam/view-as")).json() == {"stopped": False}
    ended = await world.records("view_as_stop")
    assert [(e.actor_id, e.resource_id, e.detail, e.phase) for e in ended] == [
        ("root", world.principals["carol"], "stop", "succeeded")
    ]


@pytest.mark.asyncio
async def test_sign_out_is_allowed_and_ends_the_view(world) -> None:
    root = await world.sign_in("root")
    assert (await start(root, world, "carol")).status_code == 200

    out = await root.post("/api/auth/oidc/logout")

    assert out.status_code == 200, out.text
    ended = await world.records("view_as_stop")
    assert [(e.actor_id, e.detail) for e in ended] == [("root", "sign-out")]
    async with world.sessions() as db:
        from naas_abi.apps.nexus.apps.api.app.services.view_as.adapters.secondary.sql import VIEWS

        row = (await db.execute(select(VIEWS))).one()
        assert row.ended_at is not None


@pytest.mark.asyncio
async def test_the_settings_cache_is_neither_read_nor_filled_during_a_view(world) -> None:
    root = await world.sign_in("root")
    cached = {"X-Nexus-Cache": "1"}
    assert (await root.get("/api/workspaces", headers=cached)).status_code == 200
    filled = dict(world.cache.stored)
    assert any("entry" in key for key in filled)  # outside a view it does fill
    world.cache.reads.clear()

    assert (await start(root, world, "dave")).status_code == 200
    listed = await root.get("/api/workspaces", headers=cached)

    assert [w["id"] for w in listed.json()] == [ALPHA]
    assert world.cache.reads == [] and world.cache.stored == filled
    assert "x-nexus-cache" not in listed.headers


@pytest.mark.asyncio
async def test_the_websocket_handshake_is_refused_during_a_view(world) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.websocket import runtime as ws

    root = await world.sign_in("root")
    environ = {"HTTP_COOKIE": f"nexus_session={root.session_secret}"}
    assert await ws._cookie_session_user(environ) == "root"

    assert (await start(root, world, "carol")).status_code == 200
    assert await ws._cookie_session_user(environ) is None  # no presence, no room

    await root.delete("/api/iam/view-as")
    assert await ws._cookie_session_user(environ) == "root"


# -- Ending ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_after_its_end_the_request_is_the_viewers_and_expired_is_recorded(world) -> None:
    root = await world.sign_in("root")
    assert (await start(root, world, "carol")).status_code == 200
    world.clock.now = NOW + timedelta(minutes=14, seconds=59)
    assert (await root.get("/api/auth/me")).json()["name"] == "Carol"

    world.clock.now = NOW + timedelta(minutes=15)

    me = await root.get("/api/auth/me")
    assert me.json()["name"] == "Root"
    assert (await root.post("/api/workspaces/alpha/probe")).status_code == 200  # no guard now
    assert (await root.get("/api/auth/oidc/session")).json()["view"] is None
    ended = await world.records("view_as_stop")
    assert [(e.actor_id, e.detail) for e in ended] == [("root", "expired")]  # once
    # A new view can start.
    assert (await start(root, world, "dave")).status_code == 200


@pytest.mark.asyncio
async def test_the_view_ends_when_the_viewer_no_longer_holds_the_right(world) -> None:
    carol = await world.sign_in("carol")
    world.nexus.give_features(world.principals["carol"], ["chat"], world.alpha)
    assert (await start(carol, world, "dave")).status_code == 200
    assert (await carol.get("/api/auth/me")).json()["name"] == "Dave"

    with as_service_account("api"):
        world.iam.detach_policy("builtin.admin", world.principals["carol"], world.alpha)

    assert (await carol.get("/api/auth/me")).json()["name"] == "Carol"
    ended = await world.records("view_as_stop")
    assert [e.detail for e in ended] == ["no longer allowed"]


@pytest.mark.asyncio
async def test_a_view_that_cannot_be_verified_names_nobody(world, monkeypatch) -> None:
    root = await world.sign_in("root")
    assert (await start(root, world, "carol")).status_code == 200

    async def broken(self, viewer, principal_id, container):
        raise RuntimeError("IAM is down")

    monkeypatch.setattr(view_runtime.RUNTIME.iam.__class__, "allows", broken)

    answered = await root.get("/api/auth/me")
    written = await root.post(f"/api/workspaces/{ALPHA}/probe")

    assert answered.status_code == 503 and written.status_code == 503  # never the viewer's


# -- Audit ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_start_is_audited_with_who_whom_where_until_when(world) -> None:
    await world.sign_in("carol", groups=("grp_x",), at=NOW - timedelta(hours=2))
    root = await world.sign_in("root")

    assert (await start(root, world, "carol")).status_code == 200

    records = await world.records("view_as_start")
    assert [e.phase for e in sorted(records, key=lambda e: e.phase, reverse=True)] == [
        "succeeded",
        "requested",
    ]
    entry = records[0]
    assert (entry.actor_id, entry.service, entry.resource_id) == (
        "root",
        "iam",
        world.principals["carol"],
    )
    assert f"workspace {ALPHA}" in entry.detail
    assert "ends 2026-11-06T10:15:00" in entry.detail
    assert "recorded at 2026-11-06T08:00:00" in entry.detail


@pytest.mark.asyncio
async def test_nothing_starts_when_the_audit_cannot_be_written(world) -> None:
    audit = MemoryAudit()
    audit.broken = True
    view_runtime.RUNTIME._audit = lambda: audit
    root = await world.sign_in("root")

    refused = await start(root, world, "carol")

    assert refused.status_code == 503
    assert (await root.get("/api/auth/oidc/session")).json()["view"] is None
    assert (await root.get("/api/auth/me")).json()["id"] == "root"
    async with world.sessions() as db:
        from naas_abi.apps.nexus.apps.api.app.services.view_as.adapters.secondary.sql import VIEWS

        assert (await db.execute(select(VIEWS))).all() == []


# -- Upgrade ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_database_at_the_previous_state_upgrades(world) -> None:
    carol = await world.sign_in("carol")
    from sqlalchemy import text

    async with database.async_engine.begin() as conn:
        await conn.execute(text("DROP TABLE view_as_views"))  # as before migration 0069

    await database.init_db()

    async with world.sessions() as db:
        assert (await db.execute(text("SELECT COUNT(*) FROM view_as_views"))).scalar_one() == 0
        # What the database held before is intact: the session and its user.
        assert (await db.execute(text("SELECT COUNT(*) FROM auth_sessions"))).scalar_one() >= 1
    assert (await carol.get("/api/auth/me")).json()["id"] == "carol"


# -- A view that cannot be verified ------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_and_sign_out_end_what_they_own_while_the_view_cannot_be_verified(
    world, monkeypatch
) -> None:
    root, other = await world.sign_in("root"), await world.sign_in("root")
    assert (await start(root, world, "carol")).status_code == 200
    assert (await start(other, world, "dave")).status_code == 200

    async def broken(self, viewer, principal_id, container):
        raise RuntimeError("IAM is down")

    with monkeypatch.context() as down:
        down.setattr(view_runtime.RUNTIME.iam.__class__, "allows", broken)

        assert (await root.get("/api/auth/me")).status_code == 503
        stopped = await root.delete("/api/iam/view-as")
        out = await other.post("/api/auth/oidc/logout")

    assert (stopped.status_code, stopped.json()) == (200, {"stopped": True})
    assert out.status_code == 200, out.text
    ended = await world.records("view_as_stop")
    assert sorted(e.detail for e in ended) == ["sign-out", "stop"]
    assert (await root.get("/api/auth/me")).json()["id"] == "root"  # the viewer's, no view left


# -- The person, by any of their ids ---------------------------------------------------------


@pytest.mark.asyncio
async def test_the_nexus_id_of_an_account_finds_the_person_and_iam_is_asked_by_principal(
    world,
) -> None:
    root = await world.sign_in("root")
    carol_principal = world.principals["carol"]
    assert carol_principal != "carol"

    listed = await root.get("/api/iam/view-as/workspaces", params={"principal_id": "carol"})
    started = await root.post(
        "/api/iam/view-as", json={"principal_id": "carol", "workspace_id": ALPHA}
    )

    assert [w["id"] for w in listed.json()] == [ALPHA]
    assert started.status_code == 200, started.text
    assert started.json()["person"]["id"] == carol_principal
    start_record = (await world.records("view_as_start"))[0]
    assert start_record.resource_id == carol_principal
    assert (await root.get("/api/auth/me")).json()["id"] == "carol"  # and the re-check holds
