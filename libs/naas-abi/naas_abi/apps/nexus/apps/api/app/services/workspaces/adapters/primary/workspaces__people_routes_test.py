"""People in workspaces and organizations (epic #1566): the org directory, adding
someone of it to a workspace, and the create-or-link invites.

The real routers, services, a SQLite database and a real IAM; only the people
service (accounts, mail) is the in-memory one of ``people_testing``, which still
grants through IAM on behalf of the caller.
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
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as organizations_module,
)
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    AlreadyMemberError,
    EmailTakenError,
    Grant,
    NoProviderError,
    ProvisioningFailedError,
    RetiredIdentityError,
    WorkspaceAccess,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as workspaces_module,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_testing import (
    installed,
    team_people,
)

USERS = ("owner", "admin", "member", "viewer", "stranger", "flo", "flora", "outsider", "wsadmin")
ORG = org_container("org-1")
WS1 = workspace_container("org-1", "ws-1")
WS2 = workspace_container("org-1", "ws-2")


@pytest_asyncio.fixture
async def api(team, nexus_db, monkeypatch):
    """``team`` in ws-1 of org-1, plus: ``flo`` (viewer of ws-2 only), ``flora``
    (org member, no workspace), ``wsadmin`` (admin of ws-1 only), ``outsider``
    (member of ws-9 in org-2) and ws-solo, a workspace in no organization."""
    team.grant("flo", "viewer", team.workspace("org-1", "ws-2"))
    team.grant("flora", "member", ORG)
    team.grant("wsadmin", "admin", WS1)
    team.grant("outsider", "member", team.workspace("org-2", "ws-9"))
    team.grant("owner", "owner", team.workspace(None, "ws-solo"))
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
        db.add(OrganizationModel(id="org-2", name="Other", slug="other", owner_id="outsider"))
        await db.flush()
        for ws, org in (("ws-1", "org-1"), ("ws-2", "org-1"), ("ws-9", "org-2"), ("ws-solo", None)):
            db.add(
                WorkspaceModel(
                    id=ws,
                    name=ws.upper(),
                    slug=ws,
                    owner_id="owner",
                    organization_id=org,
                    created_at=now,
                    updated_at=now,
                )
            )
        await db.commit()

    async def nothing(*_args, **_kwargs) -> None:
        return None

    for module in (workspaces_module, organizations_module):
        monkeypatch.setattr(module, "check_rate_limit", nothing)
        monkeypatch.setattr(module, "check_invitation_mail_quota", nothing)

    people = team_people(USERS)
    app = FastAPI()
    register_service_exception_handlers(app)
    app.include_router(workspaces_module.router, prefix="/api/workspaces")
    app.include_router(organizations_module.router, prefix="/api/organizations")
    current: dict[str, Any] = {"id": "admin"}

    async def session():
        async with nexus_db() as db:
            yield db
            await db.commit()

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[organizations_module._get_object_storage] = lambda: object()
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=current["id"], email=f"{current['id']}@example.com", name=current["id"].title()
    )

    def as_(user: str) -> AsyncClient:
        current["id"] = user
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    with installed(people):
        yield SimpleNamespace(as_=as_, people=people)


async def role(user: str, scope: str) -> str | None:
    return await MEMBERSHIPS.role_at(user, scope)


# -- candidates -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_candidates_are_people_of_the_org_not_yet_in_the_workspace(api) -> None:
    async with api.as_("admin") as http:
        found = await http.get("/api/workspaces/ws-1/members/candidates", params={"q": "flo"})
    assert found.status_code == 200, found.text
    items = found.json()["items"]
    assert [(i["user_id"], i["org_role"], i["status"]) for i in items] == [
        ("flo", None, "active"),
        ("flora", "member", "active"),
    ]
    assert set(items[0]) == {"user_id", "name", "email", "avatar", "status", "org_role"}


@pytest.mark.asyncio
async def test_other_organizations_and_members_already_in_never_show(api) -> None:
    async with api.as_("admin") as http:
        everyone = await http.get(
            "/api/workspaces/ws-1/members/candidates", params={"q": "example.com", "limit": 20}
        )
    shown = {i["user_id"] for i in everyone.json()["items"]}
    assert "outsider" not in shown and "stranger" not in shown
    # In ws-1 already, or reaching it through their org role (owner, admin).
    assert shown.isdisjoint({"owner", "admin", "member", "viewer", "wsadmin"})
    assert shown == {"flo", "flora"}


@pytest.mark.asyncio
async def test_candidates_need_two_characters_and_an_organization(api) -> None:
    async with api.as_("owner") as http:
        short = await http.get("/api/workspaces/ws-1/members/candidates", params={"q": "f"})
        solo = await http.get("/api/workspaces/ws-solo/members/candidates", params={"q": "flo"})
        capped = await http.get(
            "/api/workspaces/ws-1/members/candidates", params={"q": "flo", "limit": 999}
        )
    assert short.json() == {"items": []} and solo.json() == {"items": []}
    assert capped.status_code == 200
    assert [c["limit"] for c in api.people.named("search")] == [20]


@pytest.mark.asyncio
async def test_only_who_may_invite_searches(api) -> None:
    for user, allowed in (
        ("wsadmin", True),
        ("member", False),
        ("viewer", False),
        ("stranger", False),
    ):
        async with api.as_(user) as http:
            got = await http.get("/api/workspaces/ws-1/members/candidates", params={"q": "flo"})
        assert (got.status_code == 200) is allowed, (user, got.status_code)


# -- adding someone of the directory --------------------------------------------------------


@pytest.mark.asyncio
async def test_adding_a_candidate_puts_them_in_the_workspace_only(api) -> None:
    async with api.as_("wsadmin") as http:
        added = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "level": "viewer"}
        )
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["member"]["user_id"] == "flora" and body["member"]["role"] == "viewer"
    assert body["member"]["status"] == "active"
    assert body["sign_in_email_sent"] is True
    assert await role("flora", WS1) == "viewer"
    assert await role("flora", ORG) == "member"  # as before: nothing granted at the org
    (asked,) = api.people.named("add_existing")
    assert asked["grant"] == Grant(
        "org-1", level="viewer", workspaces=(WorkspaceAccess("ws-1", False),)
    )
    assert asked["by"] == "wsadmin"


@pytest.mark.asyncio
async def test_a_candidate_is_added_without_an_invitation_when_asked(api, monkeypatch) -> None:
    """Invite user's "Add to workspace": in, and no mail (so no invitation limit)."""
    counted: list[str] = []

    async def count(*_args, **_kwargs) -> None:
        counted.append("limit")

    monkeypatch.setattr(workspaces_module, "check_invitation_mail_quota", count)
    async with api.as_("wsadmin") as http:
        added = await http.post(
            "/api/workspaces/ws-1/members",
            json={"user_id": "flora", "level": "viewer", "notify": False},
        )
    assert added.status_code == 201, added.text
    assert added.json()["sign_in_email_sent"] is False
    assert await role("flora", WS1) == "viewer"
    (asked,) = api.people.named("add_existing")
    assert asked["notify"] is False and counted == []


@pytest.mark.asyncio
async def test_an_add_says_whether_the_person_was_told(api) -> None:
    """The notice is the service's to send: the answer says what happened."""
    api.people.sent = False
    async with api.as_("admin") as http:
        added = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "role": "viewer"}
        )
    assert added.status_code == 201, added.text
    assert added.json()["sign_in_email_sent"] is False


@pytest.mark.asyncio
async def test_a_workspace_only_person_is_never_given_an_org_role(api) -> None:
    async with api.as_("admin") as http:
        added = await http.post("/api/workspaces/ws-1/members", json={"user_id": "flo"})
        assert added.status_code == 201, added.text
        directory = (await http.get("/api/organizations/org-1/members")).json()
    assert await role("flo", WS1) == "member"
    assert await role("flo", ORG) is None
    row = next(m for m in directory if m["user_id"] == "flo")
    assert (row["role"], row["source"], row["status"]) == (None, "workspace", "active")


@pytest.mark.asyncio
async def test_nobody_outside_the_directory_is_found(api) -> None:
    async with api.as_("admin") as http:
        outsider = await http.post("/api/workspaces/ws-1/members", json={"user_id": "outsider"})
        unknown = await http.post("/api/workspaces/ws-1/members", json={"user_id": "nobody"})
        solo = await http.post("/api/workspaces/ws-solo/members", json={"user_id": "flo"})
    assert outsider.status_code == unknown.status_code == 404
    assert outsider.json() == unknown.json()
    assert solo.status_code in (403, 404)
    assert await role("outsider", WS1) is None
    assert api.people.named("add_existing") == []


@pytest.mark.asyncio
async def test_adding_a_member_again_is_a_conflict(api) -> None:
    async with api.as_("admin") as http:
        again = await http.post("/api/workspaces/ws-1/members", json={"user_id": "viewer"})
        org_admin = await http.post("/api/workspaces/ws-1/members", json={"user_id": "owner"})
    assert again.status_code == 409 and org_admin.status_code == 409
    assert await role("viewer", WS1) == "viewer"


@pytest.mark.asyncio
async def test_owner_is_no_longer_given_an_admin_is(api) -> None:
    for user in ("wsadmin", "owner"):
        async with api.as_(user) as http:
            refused = await http.post(
                "/api/workspaces/ws-1/members", json={"user_id": "flora", "role": "owner"}
            )
        assert refused.status_code == 400, refused.text
    assert await role("flora", WS1) is None
    async with api.as_("wsadmin") as http:
        made = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "admin": True}
        )
    assert made.status_code == 201, made.text
    assert await role("flora", WS1) == "admin"


# -- create or link -------------------------------------------------------------------------


_SHAPE = {"status", "user", "member", "provider", "sign_in_email_sent", "warning"}


@pytest.mark.asyncio
async def test_creating_and_linking_answer_alike(api) -> None:
    async with api.as_("admin") as http:
        created = await http.post(
            "/api/workspaces/ws-1/members/invite",
            json={"email": "New@Example.org", "level": "viewer", "profile": {"job_title": "CTO"}},
        )
        linked = await http.post(
            "/api/workspaces/ws-1/members/invite",
            json={"email": "outsider@example.com", "role": "viewer"},
        )
    assert created.status_code == linked.status_code == 200, (created.text, linked.text)
    for body in (created.json(), linked.json()):
        assert set(body) == _SHAPE
        assert set(body["user"]) == {"id", "email", "name", "status"}
        assert body["status"] == "added"
        assert body["member"]["role"] == "viewer"
        # The provider they sign in with, as the invitation routes answered it.
        assert body["provider"] == {
            "name": "nexus",
            "display_name": "Nexus",
            "provisioning": "builtin",
            "managed_in_provider": False,
        }
    # Someone of another organization is linked: one account, the workspace role
    # only, nothing in this organization.
    assert linked.json()["user"]["id"] == "outsider"
    assert await role("outsider", WS1) == "viewer"
    assert await role("outsider", ORG) is None
    first, _ = api.people.named("create_or_link")
    assert first["email"] == "new@example.org"
    assert first["profile"] == {"job_title": "CTO"}
    assert first["organization_id"] == "org-1"
    assert first["grant"] == Grant(
        "org-1", level="viewer", workspaces=(WorkspaceAccess("ws-1", False),)
    )


@pytest.mark.asyncio
async def test_inviting_a_member_again_is_a_conflict(api) -> None:
    async with api.as_("admin") as http:
        again = await http.post(
            "/api/workspaces/ws-1/members/invite", json={"email": "viewer@example.com"}
        )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_the_people_services_refusals_are_http_answers(api, monkeypatch) -> None:
    for error, status in (
        (NoProviderError("none"), 422),
        (ProvisioningFailedError("down"), 502),
        (AlreadyMemberError("x", "scope"), 409),
        (RetiredIdentityError("retired"), 409),
        (EmailTakenError("z@example.org"), 409),
        (ValueError("Enter a valid email address"), 400),
    ):

        async def refuse(*_args, error=error, **_kwargs):
            raise error

        monkeypatch.setattr(api.people, "create_or_link", refuse)
        async with api.as_("admin") as http:
            got = await http.post(
                "/api/workspaces/ws-1/members/invite", json={"email": "z@example.org"}
            )
        assert got.status_code == status, (error, got.text)


# -- organization invite --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_org_invite_names_workspaces_each_with_admin(api) -> None:
    async with api.as_("admin") as http:
        invited = await http.post(
            "/api/organizations/org-1/members/invite",
            json={
                "email": "outsider@example.com",
                "level": "member",
                "workspaces": [{"id": "ws-1", "admin": True}, {"id": "ws-2"}],
                "job_title": "Analyst",
            },
        )
    assert invited.status_code == 200, invited.text
    body = invited.json()
    assert set(body) == _SHAPE
    assert (body["member"]["role"], body["member"]["source"]) == (None, "workspace")
    assert await role("outsider", ORG) is None
    assert (await role("outsider", WS1), await role("outsider", WS2)) == ("admin", "member")
    (asked,) = api.people.named("create_or_link")
    assert asked["profile"] == {"job_title": "Analyst"}


@pytest.mark.asyncio
async def test_the_legacy_single_workspace_body_still_works(api) -> None:
    async with api.as_("admin") as http:
        invited = await http.post(
            "/api/organizations/org-1/members/invite",
            json={
                "email": "outsider@example.com",
                "role": "member",
                "workspace_id": "ws-2",
                "workspace_role": "viewer",
            },
        )
    assert invited.status_code == 200, invited.text
    assert await role("outsider", WS2) == "viewer"
    (asked,) = api.people.named("create_or_link")
    assert asked["grant"] == Grant(
        "org-1", level="viewer", workspaces=(WorkspaceAccess("ws-2", False),)
    )


@pytest.mark.asyncio
async def test_an_org_only_person_joins_the_orgs_people(api) -> None:
    async with api.as_("admin") as http:
        invited = await http.post(
            "/api/organizations/org-1/members/invite", json={"email": "outsider@example.com"}
        )
    assert invited.status_code == 200, invited.text
    assert invited.json()["member"]["source"] == "organization"
    assert await role("outsider", ORG) is not None
    (asked,) = api.people.named("create_or_link")
    assert asked["grant"] == Grant("org-1")


@pytest.mark.asyncio
async def test_an_org_invite_is_refused_what_it_cannot_give(api) -> None:
    async with api.as_("admin") as http:
        policies = await http.post(
            "/api/organizations/org-1/members/invite",
            json={"email": "a@x.org", "policy_ids": ["pol_y"]},
        )
        elsewhere = await http.post(
            "/api/organizations/org-1/members/invite",
            json={"email": "a@x.org", "workspaces": [{"id": "ws-9", "role": "member"}]},
        )
        owner = await http.post(
            "/api/organizations/org-1/members/invite", json={"email": "a@x.org", "role": "owner"}
        )
    assert policies.status_code == elsewhere.status_code == owner.status_code == 400
    assert api.people.named("create_or_link") == []


# -- organization access (#1589) ------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_org_admin_is_made_and_unmade_by_patch(api) -> None:
    async with api.as_("owner") as http:
        unmade = await http.patch(
            "/api/organizations/org-1/members/admin", json={"org_admin": False}
        )
        assert unmade.status_code == 200, unmade.text
        assert unmade.json()["org_admin"] is False
        assert await role("admin", ORG) == "member"
        made = await http.patch("/api/organizations/org-1/members/flora", json={"org_admin": True})
        assert made.status_code == 200, made.text
        assert made.json()["org_admin"] is True
    assert await role("flora", ORG) == "admin"


@pytest.mark.asyncio
async def test_the_last_org_admin_is_a_409(api, monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import LastOrgAdminError

    async def refuse(**_kwargs):
        raise LastOrgAdminError(ORG)

    monkeypatch.setattr(api.people, "change_access", refuse)
    async with api.as_("owner") as http:
        got = await http.patch("/api/organizations/org-1/members/admin", json={"org_admin": False})
    assert got.status_code == 409
    assert got.json()["detail"] == "An organization keeps at least one admin"


@pytest.mark.asyncio
async def test_removing_from_the_org_leaves_every_group_and_keeps_the_account(api) -> None:
    async with api.as_("admin") as http:
        gone = await http.delete("/api/organizations/org-1/members/member/access")
        again = await http.delete("/api/organizations/org-1/members/member/access")
        owner = await http.delete("/api/organizations/org-1/members/owner/access")
    assert gone.status_code == 200, gone.text
    assert gone.json() == {"message": "Removed from the organization", "workspace_ids": ["ws-1"]}
    assert await role("member", WS1) is None and await role("member", ORG) is None
    assert again.status_code == 404
    assert owner.status_code == 400  # an owner of before
    assert await role("owner", ORG) == "owner"


@pytest.mark.asyncio
async def test_capability_groups_are_listed_to_those_who_invite(api) -> None:
    async with api.as_("admin") as http:
        listed = await http.get("/api/organizations/org-1/capability-groups")
        in_ws = await http.get("/api/workspaces/ws-1/capability-groups")
    async with api.as_("viewer") as http:
        refused = await http.get("/api/organizations/org-1/capability-groups")
    assert listed.status_code == in_ws.status_code == 200, (listed.text, in_ws.text)
    assert isinstance(listed.json()["items"], list)
    assert refused.status_code == 403


# -- resend ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_is_for_invited_members_only(api) -> None:
    api.people.invited("viewer")
    async with api.as_("admin") as http:
        ws_sent = await http.post("/api/workspaces/ws-1/members/viewer/resend")
        org_sent = await http.post("/api/organizations/org-1/members/viewer/resend")
        active = await http.post("/api/workspaces/ws-1/members/member/resend")
        outside = await http.post("/api/workspaces/ws-1/members/outsider/resend")
        org_outside = await http.post("/api/organizations/org-1/members/outsider/resend")
    assert ws_sent.status_code == org_sent.status_code == 200
    assert ws_sent.json() == {"sign_in_email_sent": True}
    assert active.status_code == 409
    assert outside.status_code == org_outside.status_code == 404
    assert len(api.people.named("resend")) == 2


# -- the org directory stays the admins' ----------------------------------------------------


@pytest.mark.asyncio
async def test_a_workspace_admin_searches_their_org_but_never_lists_it(api) -> None:
    async with api.as_("wsadmin") as http:
        listed = await http.get("/api/organizations/org-1/members")
        searched = await http.get("/api/workspaces/ws-1/members/candidates", params={"q": "fl"})
        other = await http.get("/api/workspaces/ws-2/members/candidates", params={"q": "fl"})
    assert listed.status_code == 403
    assert searched.status_code == 200
    assert other.status_code in (403, 404)


@pytest.mark.asyncio
async def test_a_role_the_caller_does_not_hold_is_a_403_naming_it(api, team) -> None:
    """IAM decides what the caller may give, on the add and on the invite."""
    from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.primary.invites__primary_adapter__FastAPI_test import (  # noqa: E501
        REFUSAL,
        _inviter,
    )

    _inviter(team)
    async with api.as_("inviter") as http:
        added = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "role": "member"}
        )
        invited = await http.post(
            "/api/workspaces/ws-1/members/invite",
            json={"email": "outsider@example.com", "role": "member"},
        )
        assert added.status_code == invited.status_code == 403, (added.text, invited.text)
        for refused in (added, invited):
            assert refused.json()["detail"].startswith(REFUSAL)
            assert "builtin.member" in refused.json()["detail"]
        assert await role("flora", WS1) is None and await role("outsider", WS1) is None
        viewer = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "role": "viewer"}
        )
    assert viewer.status_code == 201, viewer.text
    assert await role("flora", WS1) == "viewer"


@pytest.mark.asyncio
async def test_an_invalid_request_the_service_refuses_is_a_400(api, monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.invites.port import InvalidPolicyError

    async def refuse(**_kwargs):
        raise InvalidPolicyError("builtin.owner is a role, not a policy")

    monkeypatch.setattr(api.people, "add_existing", refuse)
    async with api.as_("admin") as http:
        got = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "level": "member"}
        )
        policies = await http.post(
            "/api/workspaces/ws-1/members",
            json={"user_id": "flora", "policy_ids": ["builtin.owner"]},
        )
    assert got.status_code == 400
    assert "is a role" in got.json()["detail"]
    assert policies.status_code == 400
    assert "capability groups" in policies.json()["detail"]


@pytest.mark.asyncio
async def test_a_workspace_only_persons_details_are_the_org_admins_to_read(api) -> None:
    """Org › Users lists them, and links to their page: it serves them, with no org
    role, as someone reached through a workspace."""
    async with api.as_("admin") as http:
        details = await http.get("/api/organizations/org-1/members/flo")
        outside = await http.get("/api/organizations/org-1/members/outsider")
    async with api.as_("wsadmin") as http:
        refused = await http.get("/api/organizations/org-1/members/flo")
    assert details.status_code == 200, details.text
    body = details.json()
    assert (body["member"]["role"], body["member"]["source"]) == (None, "workspace")
    assert body["member"]["status"] == "active"
    assert [(w["id"], w["role"]) for w in body["workspaces"] if w["role"]] == [("ws-2", "viewer")]
    assert outside.status_code == 404
    assert refused.status_code == 403


# -- remove from organization --------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_workspace_only_person_is_removed_from_the_organization_in_one_step(api) -> None:
    """Org settings › Users › Remove from organization: every workspace of the org
    in one step. Their account stays, and so does what they hold elsewhere."""
    await MEMBERSHIPS.grant("flo", "viewer", WS1)
    await MEMBERSHIPS.grant("flo", "member", workspace_container("org-2", "ws-9"))
    async with api.as_("admin") as http:
        # Not an org role to take (the org-role removal is the other route).
        org_role_only = await http.delete("/api/organizations/org-1/members/flo")
        removed = await http.delete("/api/organizations/org-1/members/flo/access")
        directory = (await http.get("/api/organizations/org-1/members")).json()
        again = await http.delete("/api/organizations/org-1/members/flo/access")
    assert org_role_only.status_code == 404
    assert removed.status_code == 200, removed.text
    assert sorted(removed.json()["workspace_ids"]) == ["ws-1", "ws-2"]
    assert "flo" not in {m["user_id"] for m in directory}
    assert await MEMBERSHIPS.roles_of("flo") == {workspace_container("org-2", "ws-9"): "member"}
    assert again.status_code == 404
    assert await api.people.get("flo") is not None


@pytest.mark.asyncio
async def test_removing_from_the_organization_takes_any_org_role_too(api) -> None:
    async with api.as_("admin") as http:
        removed = await http.delete("/api/organizations/org-1/members/member/access")
    assert removed.status_code == 200, removed.text
    assert removed.json()["workspace_ids"] == ["ws-1"]
    assert await role("member", ORG) is None and await role("member", WS1) is None


@pytest.mark.asyncio
async def test_an_org_owner_is_never_removed_from_the_organization_this_way(api) -> None:
    async with api.as_("admin") as http:
        refused = await http.delete("/api/organizations/org-1/members/owner/access")
    async with api.as_("owner") as http:
        themselves = await http.delete("/api/organizations/org-1/members/owner/access")
    assert refused.status_code == 400, refused.text
    assert themselves.status_code == 400, themselves.text
    assert await role("owner", ORG) == "owner" and await role("owner", WS1) == "owner"


@pytest.mark.asyncio
async def test_only_who_may_remove_org_members_removes_from_the_organization(api) -> None:
    for user in ("wsadmin", "member", "stranger"):
        async with api.as_(user) as http:
            refused = await http.delete("/api/organizations/org-1/members/flo/access")
        assert refused.status_code == 403, (user, refused.text)
    assert await role("flo", WS2) == "viewer"
    async with api.as_("admin") as http:
        outside = await http.delete("/api/organizations/org-1/members/outsider/access")
    assert outside.status_code == 404


@pytest.mark.asyncio
async def test_a_workspace_owner_leaves_only_by_an_owner_and_never_as_the_last(api) -> None:
    """Every change is checked before the first: a refusal changes nothing."""
    await MEMBERSHIPS.grant("flo", "owner", WS2)
    await MEMBERSHIPS.grant("flo", "member", WS1)
    async with api.as_("admin") as http:
        by_admin = await http.delete("/api/organizations/org-1/members/flo/access")
    async with api.as_("owner") as http:
        last = await http.delete("/api/organizations/org-1/members/flo/access")
    assert by_admin.status_code == 403, by_admin.text
    assert last.status_code == 409, last.text
    assert "WS-2" in last.json()["detail"]
    assert await role("flo", WS2) == "owner" and await role("flo", WS1) == "member"
    await MEMBERSHIPS.grant("owner", "owner", WS2)
    async with api.as_("owner") as http:
        removed = await http.delete("/api/organizations/org-1/members/flo/access")
    assert removed.status_code == 200, removed.text
    assert await role("flo", WS2) is None and await role("flo", WS1) is None
