"""Workspaces and organizations on IAM: viewers read, owners are protected.

The real routers, services and a SQLite database, with a real IAM whose roles
are attachments: nothing about who may do what is mocked.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.exceptions import (
    register_service_exception_handlers,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_scope, workspace_scope
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as organizations_module,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary.organizations__primary_adapter__FastAPI import (  # noqa: E501
    router as organizations_router,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as workspaces_module,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.workspaces__primary_adapter__FastAPI import (  # noqa: E501
    router as workspaces_router,
)
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    service_account,
    use_call_context,
)
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER

USERS = ("owner", "admin", "member", "viewer", "stranger", "bob")


@pytest_asyncio.fixture
async def api(team, nexus_db, monkeypatch):
    now = datetime(2026, 1, 1)
    async with nexus_db() as db:
        for user in USERS:
            db.add(
                UserModel(
                    id=user,
                    email=f"{user}@example.com",
                    name=user.title(),
                    created_at=now,
                    updated_at=now,
                )
            )
        db.add(OrganizationModel(id="org-1", name="Org", slug="org", owner_id="owner"))
        await db.flush()
        db.add(
            WorkspaceModel(
                id="ws-1",
                name="WS",
                slug="ws",
                owner_id="owner",
                organization_id="org-1",
                created_at=now,
                updated_at=now,
            )
        )
        await db.commit()

    # Rate limits and the notice mail live elsewhere: out of scope here.
    async def no_limit(*_args, **_kwargs) -> None:
        return None

    async def no_mail(*_args, **_kwargs) -> bool:
        return False

    async def no_seeding(**_kwargs) -> None:
        return None

    monkeypatch.setattr(workspaces_module, "seed_workspace_agents", no_seeding)
    for module in (workspaces_module, organizations_module):
        monkeypatch.setattr(module, "check_rate_limit", no_limit)
        monkeypatch.setattr(module, "send_added_notice", no_mail)

    app = FastAPI()
    register_service_exception_handlers(app)  # as main.py does
    app.include_router(workspaces_router, prefix="/api/workspaces")
    app.include_router(organizations_router, prefix="/api/organizations")
    current: dict[str, Any] = {"id": "member", "scope": None}

    @app.middleware("http")
    async def credential(request, call_next):
        """A personal key's request: ``api`` for the user, narrowed by the key."""
        if current["scope"] is None:
            return await call_next(request)
        context = CallContext(
            principal=service_account("api"),
            on_behalf_of=Principal(id=current["id"], kind="user"),
            scope=current["scope"],
        )
        with use_call_context(context):
            return await call_next(request)

    async def session():
        async with nexus_db() as db:
            yield db
            await db.commit()

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[workspaces_module.get_service_registry] = lambda: SimpleNamespace(
        agents=None
    )
    # The drive profile sync (best effort) has no object storage here.
    app.dependency_overrides[organizations_module._get_object_storage] = lambda: object()
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=current["id"], email=f"{current['id']}@example.com", name=current["id"].title()
    )

    def as_(user: str, scope: Any = None) -> AsyncClient:
        current["id"], current["scope"] = user, scope
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return as_


async def role(user: str, scope: str) -> str | None:
    return await MEMBERSHIPS.role_at(user, scope)


WS = workspace_scope("org-1", "ws-1")
ORG = org_scope("org-1")


# -- workspaces: who sees and does what ---------------------------------------------------


@pytest.mark.asyncio
async def test_workspace_listing_shows_only_what_roles_reach(api) -> None:
    async with api("viewer") as http:
        found = (await http.get("/api/workspaces")).json()
        assert [(w["id"], w["current_user_role"]) for w in found] == [("ws-1", "viewer")]
    async with api("stranger") as http:
        assert (await http.get("/api/workspaces")).json() == []
        assert (await http.get("/api/workspaces/ws-1")).status_code == 403


@pytest.mark.asyncio
async def test_a_viewer_reads_a_workspace_and_changes_nothing(api) -> None:
    async with api("viewer") as http:
        assert (await http.get("/api/workspaces/ws-1")).status_code == 200
        assert (await http.get("/api/workspaces/ws-1/stats")).status_code == 200
        members = await http.get("/api/workspaces/ws-1/members")
        assert {m["user_id"]: m["role"] for m in members.json()} == {
            "owner": "owner",
            "admin": "admin",
            "member": "member",
            "viewer": "viewer",
        }
        # The settings section is not among a viewer's features: the API refuses it.
        features = await http.get("/api/workspaces/ws-1/servers")
        assert features.status_code == 403
        assert "not available" in features.json()["detail"]
        for method, path, body in (
            ("patch", "/api/workspaces/ws-1", {"name": "x"}),
            ("delete", "/api/workspaces/ws-1", None),
            ("post", "/api/workspaces/ws-1/members/invite", {"email": "bob@example.com"}),
            ("patch", "/api/workspaces/ws-1/members/member", {"role": "admin"}),
            ("delete", "/api/workspaces/ws-1/members/member", None),
            (
                "post",
                "/api/workspaces/ws-1/servers",
                {"name": "s", "type": "custom", "endpoint": "http://x"},
            ),
        ):
            sent = await http.request(method.upper(), path, json=body)
            assert sent.status_code == 403, (method, path, sent.text)


@pytest.mark.asyncio
async def test_members_and_admins_hold_their_own_level(api) -> None:
    async with api("member") as http:
        assert (await http.get("/api/workspaces/ws-1/members")).status_code == 200
        assert (await http.patch("/api/workspaces/ws-1", json={"name": "x"})).status_code == 403
    async with api("admin") as http:
        assert (
            await http.patch("/api/workspaces/ws-1", json={"name": "Renamed"})
        ).status_code == 200
        assert (await http.get("/api/workspaces/ws-1/servers")).status_code == 200
        assert (await http.delete("/api/workspaces/ws-1")).status_code == 403  # the owner's
    async with api("owner") as http:
        assert (await http.delete("/api/workspaces/ws-1")).status_code == 200
        assert await role("owner", WS) is None  # the scope's roles went with it


# -- creating a workspace needs the right on the organization -------------------


@pytest.mark.asyncio
async def test_a_workspace_is_created_only_in_an_organization_the_caller_may(api) -> None:
    body = {"name": "Mine", "slug": "mine", "organization_id": "org-1"}
    async with api("stranger") as http:
        refused = await http.post("/api/workspaces", json=body)
        assert refused.status_code == 403
        assert "organization" in refused.json()["detail"]
    async with api("viewer") as http:
        assert (await http.post("/api/workspaces", json=body)).status_code == 403
    # Creating a workspace in an organization is for its owners and admins.
    async with api("member") as http:
        assert (await http.post("/api/workspaces", json=body)).status_code == 403
    async with api("admin") as http:
        made = await http.post("/api/workspaces", json=body)
        assert made.status_code == 200, made.text
        created = made.json()
        assert created["organization_id"] == "org-1"
        assert created["current_user_role"] == "owner"
    # The creator owns it, nobody else holds a role there.
    scope = workspace_scope("org-1", created["id"])
    assert await role("admin", scope) == "owner"
    assert await role("owner", scope) is None


@pytest.mark.asyncio
async def test_a_workspace_without_an_organization_is_the_callers_own(api) -> None:
    async with api("stranger") as http:
        made = await http.post("/api/workspaces", json={"name": "Solo", "slug": "solo"})
        assert made.status_code == 200, made.text
        assert made.json()["organization_id"] is None
        workspace = made.json()["id"]
        assert (await http.get(f"/api/workspaces/{workspace}")).status_code == 200
    async with api("member") as http:
        assert (await http.get(f"/api/workspaces/{workspace}")).status_code == 403


# -- the owner's role is the owner's ---------------------------------------------


@pytest.mark.asyncio
async def test_an_admin_cannot_grant_demote_or_remove_a_workspace_owner(api) -> None:
    async with api("admin") as http:
        grant = await http.post(
            "/api/workspaces/ws-1/members/invite",
            json={"email": "bob@example.com", "role": "owner"},
        )
        assert grant.status_code == 403
        assert "owners" in grant.json()["detail"]
        assert await role("bob", WS) is None
        demote = await http.patch("/api/workspaces/ws-1/members/owner", json={"role": "member"})
        assert demote.status_code == 403
        remove = await http.delete("/api/workspaces/ws-1/members/owner")
        assert remove.status_code == 403
        promote = await http.patch("/api/workspaces/ws-1/members/member", json={"role": "owner"})
        assert promote.status_code == 403
    assert await role("owner", WS) == "owner"
    assert await role("member", WS) == "member"
    # An admin still runs the roles below owner.
    async with api("admin") as http:
        assert (
            await http.patch("/api/workspaces/ws-1/members/member", json={"role": "viewer"})
        ).status_code == 200
        assert (await http.delete("/api/workspaces/ws-1/members/viewer")).status_code == 200
        invited = await http.post(
            "/api/workspaces/ws-1/members/invite", json={"email": "bob@example.com"}
        )
        assert invited.status_code == 200, invited.text
    assert await role("bob", WS) == "member"
    assert await role("member", WS) == "viewer"


@pytest.mark.asyncio
async def test_owners_manage_owners_but_the_last_one_stays(api) -> None:
    async with api("owner") as http:
        assert (
            await http.patch("/api/workspaces/ws-1/members/admin", json={"role": "owner"})
        ).status_code == 200
        assert await role("admin", WS) == "owner"
        assert (
            await http.patch("/api/workspaces/ws-1/members/admin", json={"role": "member"})
        ).status_code == 200
        assert await role("admin", WS) == "member"
        # Cannot remove or demote yourself, and the only owner is never demoted.
        assert (await http.delete("/api/workspaces/ws-1/members/owner")).status_code == 400
    async with api("admin") as http:
        assert (
            await http.patch("/api/workspaces/ws-1/members/owner", json={"role": "member"})
        ).status_code == 403


def _users_in_iam(team) -> int:
    return len(team.iam.store.list_principals("user", limit=1000, after=None).items)


@pytest.mark.asyncio
async def test_an_id_from_a_path_never_becomes_an_iam_user(api, team, monkeypatch) -> None:
    async def known(user_id: str) -> bool:
        return user_id in USERS

    monkeypatch.setattr(MEMBERSHIPS, "known_user", known)
    before = _users_in_iam(team)
    async with api("owner") as http:
        assert (
            await http.patch("/api/workspaces/ws-1/members/nobody", json={"role": "admin"})
        ).status_code == 404
        assert (await http.delete("/api/workspaces/ws-1/members/nobody")).status_code == 404
        assert (await http.get("/api/workspaces/ws-1/members")).status_code == 200
    assert await MEMBERSHIPS.roles_of("nobody") == {}
    await MEMBERSHIPS.check("nobody", "admin", WS)
    assert await MEMBERSHIPS.revoke("nobody", WS) is False
    assert _users_in_iam(team) == before


@pytest.mark.asyncio
async def test_roles_are_never_attached_to_a_service_account(team, monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import UnknownUserError
    from naas_abi_core.engine.call_context import as_service_account

    with as_service_account("engine"):
        account = team.iam.create_service_account("ci-bot")

    async def known(user_id: str) -> bool:
        return False

    monkeypatch.setattr(MEMBERSHIPS, "known_user", known)
    with pytest.raises(UnknownUserError):
        await MEMBERSHIPS.grant(account.id, "member", WS)
    with pytest.raises(UnknownUserError):
        await MEMBERSHIPS.grant("somebody-not-in-nexus", "member", WS)
    assert await MEMBERSHIPS.roles_of(account.id) == {}
    with as_service_account("engine"):
        assert not [a for a in team.iam.list_attachments(principal_id=account.id) if a.scope == WS]


# -- a failed create takes back what it did -----------------------------------------------


class _IamRefuses(Exception):
    pass


def _scope_orgs(team) -> set[str]:
    return {scope.org for scope in team.iam.store.list_scopes()}


@pytest.mark.asyncio
async def test_an_organization_whose_owner_cannot_be_set_is_not_left_behind(
    team, nexus_db, monkeypatch
) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (  # noqa: E501
        OrganizationSecondaryAdapterPostgres,
    )
    from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
        OrganizationService,
    )
    from sqlalchemy import select

    async def refuse(*_args, **_kwargs) -> None:
        raise _IamRefuses

    monkeypatch.setattr(MEMBERSHIPS, "grant", refuse)
    known = _scope_orgs(team)
    async with nexus_db() as db:
        service = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        with pytest.raises(_IamRefuses):
            await service.create_organization(
                name="Lost", slug="lost", owner_id="owner", now=datetime(2026, 1, 1)
            )
        # The row is gone before any commit could keep it, and IAM forgot the scope.
        rows = await db.execute(select(OrganizationModel).where(OrganizationModel.slug == "lost"))
        assert rows.first() is None
    assert _scope_orgs(team) == known


# -- organizations ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_org_directory_is_for_owners_and_admins(api) -> None:
    for user, allowed in (("owner", True), ("admin", True), ("member", False), ("viewer", False)):
        async with api(user) as http:
            seen = {
                "members": (await http.get("/api/organizations/org-1/members")).status_code,
                "domains": (await http.get("/api/organizations/org-1/domains")).status_code,
                "billing": (await http.get("/api/organizations/org-1/billing")).status_code,
                "org": (await http.get("/api/organizations/org-1")).status_code,
            }
        assert seen["org"] == 200, user
        if allowed:
            assert seen["members"] == 200 and seen["domains"] == 200
            assert seen["billing"] == 501  # reaches the route: not implemented yet
        else:
            assert seen == {"members": 403, "domains": 403, "billing": 403, "org": 200}, user


@pytest.mark.asyncio
async def test_an_org_admin_cannot_make_demote_or_remove_an_org_owner(api) -> None:
    async with api("admin") as http:
        invited = await http.post(
            "/api/organizations/org-1/members/invite",
            json={"email": "bob@example.com", "role": "owner"},
        )
        assert invited.status_code == 403
        assert await role("bob", ORG) is None
        assert (
            await http.patch("/api/organizations/org-1/members/owner", json={"role": "member"})
        ).status_code == 403
        assert (await http.delete("/api/organizations/org-1/members/owner")).status_code == 400
        # Members below owner are the admin's to manage.
        assert (
            await http.patch("/api/organizations/org-1/members/member", json={"role": "admin"})
        ).status_code == 200
        added = await http.post(
            "/api/organizations/org-1/members/invite", json={"email": "bob@example.com"}
        )
        assert added.status_code == 200, added.text
    assert await role("owner", ORG) == "owner"
    assert await role("bob", ORG) == "member"
    assert await role("member", ORG) == "admin"
    async with api("owner") as http:
        assert (
            await http.patch("/api/organizations/org-1/members/admin", json={"role": "owner"})
        ).status_code == 200
        assert await role("admin", ORG) == "owner"


@pytest.mark.asyncio
async def test_a_viewer_changes_nothing_in_an_organization(api) -> None:
    async with api("viewer") as http:
        for method, path, body in (
            ("patch", "/api/organizations/org-1", {"name": "x"}),
            ("post", "/api/organizations/org-1/domains", {"domain": "example.org"}),
        ):
            sent = await http.request(method.upper(), path, json=body)
            assert sent.status_code == 403, (method, path, sent.text)


# -- ids that name no workspace -------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_orgs_own_scope_is_never_a_workspace_of_the_path(api) -> None:
    """``-`` is how an organization's own scope is written: a path naming it is not
    the organization's members' workspace, whatever role the org gives."""
    for user in ("member", "viewer", "admin", "owner", "stranger"):
        async with api(user) as http:
            for path in (
                "/api/workspaces/-/members",
                "/api/workspaces/*/members",
                "/api/workspaces/_none/members",
                "/api/workspaces/-",
            ):
                got = await http.get(path)
                assert got.status_code in (403, 404), (user, path, got.status_code)
    # The org's directory is still the admins' own route.
    async with api("viewer") as http:
        assert (await http.get("/api/organizations/org-1/members")).status_code == 403
    async with api("admin") as http:
        assert (await http.get("/api/organizations/org-1/members")).status_code == 200
        # Nor can an org role be edited through a workspace route naming the org scope.
        assert (
            await http.patch("/api/workspaces/-/members/bob", json={"role": "member"})
        ).status_code in (403, 404)
        assert await role("bob", ORG) is None
    assert await AUTHZ.org_of("-") is None and await AUTHZ.org_of("*") is None
    assert await AUTHZ.org_of("ws-1") == "org-1"


# -- grant only what you hold -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_key_that_only_reads_gives_no_role_that_writes(api) -> None:
    """A personal key narrows what its owner may grant: an admin's read-only key
    (that may still attach) makes no member, which writes."""
    reads_and_attaches = [
        {
            "effect": "Allow",
            "actions": [
                "nexus:*",
                "*:List*",
                "*:Get*",
                "*:Query*",
                "*:Read*",
                "iam:AttachPolicy",
                "iam:DetachPolicy",
            ],
            "resources": ["*"],
        }
    ]
    async with api("admin", scope=reads_and_attaches) as http:
        refused = await http.patch("/api/workspaces/ws-1/members/viewer", json={"role": "member"})
        assert refused.status_code == 403, refused.text
        assert "the scope of your credential does not allow it" in refused.json()["detail"]
    assert await role("viewer", WS) == "viewer"
    async with api("admin") as http:
        granted = await http.patch("/api/workspaces/ws-1/members/viewer", json={"role": "member"})
        assert granted.status_code == 200, granted.text
    assert await role("viewer", WS) == "member"


async def _second_workspace(team, nexus_db) -> str:
    async with nexus_db() as db:
        now = datetime(2026, 1, 1)
        db.add(
            WorkspaceModel(
                id="ws-2",
                name="WS 2",
                slug="ws-2",
                owner_id="owner",
                organization_id="org-1",
                created_at=now,
                updated_at=now,
            )
        )
        await db.commit()
    return team.workspace("org-1", "ws-2")


def _give(team, user: str, *statements: dict) -> None:
    """A policy of literal resources, attached to ``user`` unscoped."""
    with as_service_account("engine"):
        principal = team.iam.ensure_user(LEGACY_NEXUS_ISSUER, user, provider="nexus")
        policy = team.iam.create_policy(
            f"{user} extra", {"version": "2026-10-13", "statements": list(statements)}
        )
        team.iam.attach_policy(policy.id, principal.id)


@pytest.mark.asyncio
async def test_assigning_workspaces_is_checked_at_each_workspace(api, team, nexus_db) -> None:
    """``PUT /organizations/<org>/members/<user>/workspaces`` changes roles as the
    caller, at each workspace: the right to update an org member alone gives no
    workspace role, and no one gives one granting more than they hold."""
    ws2 = await _second_workspace(team, nexus_db)
    assign = {"workspace_ids": ["ws-1", "ws-2"], "workspace_role": "admin"}
    _give(
        team,
        "viewer",
        {
            "effect": "Allow",
            "actions": ["nexus:UpdateOrganizationMember"],
            "resources": ["abi:org-1:-:nexus:member/*"],
        },
    )
    async with api("viewer") as http:
        refused = await http.put("/api/organizations/org-1/members/viewer/workspaces", json=assign)
        assert refused.status_code == 403, refused.text
    assert await role("viewer", ws2) is None
    # May attach admin anywhere in the org, without holding what admin grants.
    _give(
        team,
        "viewer",
        {
            "effect": "Allow",
            "actions": ["iam:AttachPolicy", "iam:DetachPolicy"],
            "resources": ["abi:org-1:*:iam:attachment/*"],
        },
    )
    async with api("viewer") as http:
        refused = await http.put("/api/organizations/org-1/members/member/workspaces", json=assign)
        assert refused.status_code == 403, refused.text
        detail = refused.json()["detail"]
        assert detail.startswith("You cannot grant what you do not hold"), detail
        assert "builtin.admin" in detail, detail
    assert await role("member", ws2) is None
    # An org admin assigns through the org-wide role.
    async with api("admin") as http:
        granted = await http.put("/api/organizations/org-1/members/member/workspaces", json=assign)
        assert granted.status_code == 200, granted.text
        assert granted.json()["added"] == ["ws-2"]
    assert await role("member", ws2) == "admin"
