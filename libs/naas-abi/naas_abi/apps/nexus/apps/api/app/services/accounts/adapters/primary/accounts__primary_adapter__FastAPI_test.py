"""Platform Settings > Users through its routes, on a real IAM and Nexus's tables
(SQLite), with the identity provider in memory: who sees the directory, the
lifecycle of an account and of an invitation, and the rules nobody gets around."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import (
    AuthSessionModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts import runtime as accounts_runtime
from naas_abi.apps.nexus.apps.api.app.services.accounts.adapters.primary.accounts__primary_adapter__FastAPI import (  # noqa: E501
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.adapters.secondary.engine import (
    EngineAccessGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.adapters.secondary.invitations import (
    InvitationsAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.adapters.secondary.postgres import (
    AccountStorePostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.port import (
    IdentityGateway,
    Provider,
    ProviderAccount,
    ProviderManaged,
    ProviderUnreachable,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.service import AccountService
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.engine import (
    EngineGrantsGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.postgres import (
    InvitationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    Directory,
    DirectoryGateway,
    ProviderChoice,
    Provisioned,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService
from naas_abi.apps.nexus.apps.api.app.services.invites.service_test import Mailer
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
from naas_abi_core.services.identity.IdentityPorts import (
    ProviderUnavailableError,
    ProvisioningError,
)

NOW = datetime(2026, 11, 4, 12, 0)
BUILTIN = ProviderChoice("builtin", "Built-in", "builtin")


@dataclass
class Person:
    subject: str
    name: str
    disabled: bool = False


class Idp(DirectoryGateway, IdentityGateway):
    """One identity provider in memory: invitations make people there, and the
    directory disables, renames and deletes them."""

    def __init__(self) -> None:
        self.people: dict[str, Person] = {}
        self.managed = False
        # What provisioning raises (a provider down, an address it refuses).
        self.provision_fails: Exception | None = None
        self.delete_fails = False

    def subject_of(self, email: str) -> str:
        return self.people[email].subject

    def by_subject(self, subject: str) -> tuple[str, Person] | None:
        return next(((e, p) for e, p in self.people.items() if p.subject == subject), None)

    # -- invitations' side
    async def directory(self) -> Directory:
        return Directory(providers=(BUILTIN,), default="builtin")

    async def provision(self, provider, email, name, *, by=None):
        if self.provision_fails is not None:
            raise self.provision_fails
        created = email not in self.people
        if created:
            self.people[email] = Person(f"sub-{email.split('@')[0]}", name or email)
        return Provisioned(subject=self.people[email].subject, created=created)

    # -- the directory's side
    async def providers(self) -> list[Provider]:
        return [Provider("builtin", "Built-in", managed_in_provider=self.managed)]

    async def find(self, provider: str, email: str, *, by: str) -> ProviderAccount | None:
        if self.managed:
            raise ProviderManaged("managed")
        person = self.people.get(email)
        if person is None:
            return None
        return ProviderAccount(provider, person.subject, person.name, person.disabled)

    async def update(self, provider, subject, *, name=None, disabled=None, by):
        found = self.by_subject(subject)
        if found is None:
            return None
        _, person = found
        if name is not None:
            person.name = name
        if disabled is not None:
            person.disabled = disabled
        return ProviderAccount(provider, subject, person.name, person.disabled)

    async def delete(self, provider, subject, *, by):
        if self.delete_fails:
            raise ProviderUnreachable("the provider is down")
        found = self.by_subject(subject)
        if found is None:
            return False
        del self.people[found[0]]
        return True


USERS = ("root", "owner", "admin", "member", "viewer", "stranger", "operator")


def _operator(team, actions: list[str]) -> None:
    """``operator`` holds ``actions`` on every account and principal, at the platform,
    without being a platform admin."""
    with as_service_account("engine"):
        operator = team.iam.ensure_user(LEGACY_NEXUS_ISSUER, "operator", provider="nexus")
        policy = team.iam.create_policy(
            f"operator {len(actions)}",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": actions,
                        "resources": ["abi:nexus:user/*", "abi:iam:principal/*"],
                    }
                ],
            },
        )
        team.iam.attach_policy(policy.id, operator.id)


@pytest_asyncio.fixture
async def api(team, nexus_db):
    team.platform_admin("root")
    team.user("operator")
    async with nexus_db() as db:
        for user in USERS:
            signed_in = user not in ("viewer",)
            db.add(
                UserModel(
                    id=user,
                    email=f"{user}@example.com",
                    name=user.title(),
                    idp_provider="builtin" if signed_in else None,
                    idp_issuer="https://idp" if signed_in else None,
                    idp_subject=f"sub-{user}" if signed_in else None,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        db.add(OrganizationModel(id="org-1", name="Acme", slug="acme", owner_id="owner"))
        await db.flush()
        db.add(
            WorkspaceModel(
                id="ws-1",
                name="Research",
                slug="research",
                owner_id="owner",
                organization_id="org-1",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            AuthSessionModel(
                id="s" * 64,
                user_id="member",
                principal_id="x",
                provider="builtin",
                refresh_at=NOW,
                expires_at=datetime.now() + timedelta(days=1),
                created_at=NOW,
            )
        )
        await db.commit()

    idp = Idp()
    for user in USERS:
        if user != "viewer":
            idp.people[f"{user}@example.com"] = Person(f"sub-{user}", user.title())
    audit = MemoryAudit()
    access = EngineAccessGateway()

    def service(db) -> AccountService:
        # As in production: the accounts and the invitations share the request's session.
        invitations = InvitationService(
            InvitationSecondaryAdapterPostgres(db),
            idp,
            EngineGrantsGateway(lambda: team.iam),
            Mailer(),
            sign_in_url=lambda email, provider: f"https://web/login?email={email}",
            clock=lambda: NOW,
        )
        return AccountService(
            AccountStorePostgres(db),
            access,
            idp,
            InvitationsAdapter(invitations),
            audit,
            clock=lambda: NOW,
        )

    app = FastAPI()
    app.include_router(router, prefix="/api/admin/users")
    current: dict[str, Any] = {"id": "root"}

    async def session():
        async with nexus_db() as db:
            yield db
            await db.commit()

    app.dependency_overrides[get_db] = session

    async def account_service():
        async with nexus_db() as db:
            yield service(_one_at_a_time(db))

    app.dependency_overrides[accounts_runtime.get_account_service] = account_service
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=current["id"], email=f"{current['id']}@example.com", name=current["id"].title()
    )

    def as_(user: str) -> AsyncClient:
        current["id"] = user
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return SimpleNamespace(as_=as_, idp=idp, audit=audit, db=nexus_db)


def _one_at_a_time(db):
    """The request's session, refusing what Postgres (asyncpg) refuses: a second
    operation while one is running. SQLite would let it through."""
    running = {"now": False}
    execute = db.execute

    async def guarded(*args, **kwargs):
        if running["now"]:
            raise AssertionError("the session is used by two operations at once")
        running["now"] = True
        try:
            return await execute(*args, **kwargs)
        finally:
            running["now"] = False

    db.execute = guarded
    return db


def _status(team, user: str) -> str:
    with as_service_account("api"):
        record = team.iam.resolve_user(user)
    return record.status


def _phases(audit: MemoryAudit, operation: str) -> list[str]:
    return [r.phase for r in audit.records if r.action.operation == operation]


# -- the directory --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_platform_admin_lists_every_account(api, team):
    """The list reads Nexus's rows and invitations on one session, never at once."""
    async with api.as_("root") as http:
        await http.post("/api/admin/users/invite", json={"email": "erin@example.com"})
        response = await http.get("/api/admin/users")
    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in response.json()}
    assert set(rows) >= set(USERS)
    root, member, viewer = rows["root"], rows["member"], rows["viewer"]
    assert root["is_superadmin"] and not member["is_superadmin"]
    assert member["status"] == "signed_in" and viewer["status"] == "invited"
    assert member["principal_id"] == team.principal("member") != "member"
    assert member["organizations"] == [{"id": "org-1", "name": "Acme", "role": "member"}]
    assert not member["deactivated"] and member["kind"] == "account"


@pytest.mark.asyncio
@pytest.mark.parametrize("user", ["owner", "admin", "member", "stranger"])
async def test_nobody_else_sees_the_directory(api, user):
    """An organization's owner or admin is no platform admin: no page, no answer."""
    async with api.as_(user) as http:
        assert (await http.get("/api/admin/users")).status_code == 403
        refused = await http.post("/api/admin/users/member/deactivate")
        assert refused.status_code == 403
        assert (await http.delete("/api/admin/users/member?confirm=x")).status_code == 403


# -- invitations ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_invitation_is_listed_and_deactivated_at_the_provider(api):
    async with api.as_("root") as http:
        invited = await http.post(
            "/api/admin/users/invite", json={"email": "Carl@Example.com", "name": "Carl"}
        )
        assert invited.status_code == 200, invited.text
        body = invited.json()
        assert body["user_created"] and body["user"]["kind"] == "invitation"
        assert body["user"]["id"] == "invited:carl@example.com"
        assert body["user"]["status"] == "invited" and body["user"]["principal_id"] is None
        rows = {row["id"]: row for row in (await http.get("/api/admin/users")).json()}
        assert rows["invited:carl@example.com"]["name"] == "Carl"

        account = quote("invited:carl@example.com", safe="")
        off = await http.post(f"/api/admin/users/{account}/deactivate")
        assert off.status_code == 200, off.text
        assert off.json()["deactivated"] is True
        assert api.idp.people["carl@example.com"].disabled  # sign-in refused there
        on = await http.post(f"/api/admin/users/{account}/reactivate")
        assert on.json()["deactivated"] is False
        assert not api.idp.people["carl@example.com"].disabled
    assert _phases(api.audit, "invite_user") == ["requested", "succeeded"]
    assert _phases(api.audit, "suspend_user") == ["requested", "succeeded"]


@pytest.mark.asyncio
async def test_an_address_with_an_account_is_not_invited_again(api):
    async with api.as_("root") as http:
        response = await http.post("/api/admin/users/invite", json={"email": "member@example.com"})
    assert response.status_code == 409
    assert "already has an account" in response.json()["detail"]


@pytest.mark.asyncio
async def test_an_invitation_is_deleted_with_its_account_at_the_provider(api):
    async with api.as_("root") as http:
        await http.post("/api/admin/users/invite", json={"email": "dana@example.com"})
        account = quote("invited:dana@example.com", safe="")
        plan = (await http.get(f"/api/admin/users/{account}/deletion")).json()
        assert plan["blocked"] is None and plan["goes"]["invitations"] == 1
        assert plan["goes"]["provider_account"]["provider"] == "builtin"
        gone = await http.delete(f"/api/admin/users/{account}?confirm=dana@example.com")
        assert gone.status_code == 200, gone.text
        ids = {row["id"] for row in (await http.get("/api/admin/users")).json()}
    assert "invited:dana@example.com" not in ids
    assert "dana@example.com" not in api.idp.people


# -- deactivating and reactivating ------------------------------------------------------------


@pytest.mark.asyncio
async def test_deactivating_suspends_in_iam_disables_at_the_provider_and_ends_sessions(api, team):
    async with api.as_("root") as http:
        off = await http.post("/api/admin/users/member/deactivate")
        assert off.status_code == 200, off.text
        assert off.json()["deactivated"] is True
        assert _status(team, "member") == "suspended"
        assert api.idp.people["member@example.com"].disabled
        async with api.db() as db:
            session = await db.get(AuthSessionModel, "s" * 64)
            assert session.revoked_at is not None
        # Data and memberships stay.
        rows = {row["id"]: row for row in (await http.get("/api/admin/users")).json()}
        assert rows["member"]["organizations"] and rows["member"]["deactivated"]

        on = await http.post("/api/admin/users/member/reactivate")
        assert on.json()["deactivated"] is False
    assert _status(team, "member") == "active"
    assert not api.idp.people["member@example.com"].disabled
    assert _phases(api.audit, "resume_user") == ["requested", "succeeded"]


@pytest.mark.asyncio
async def test_nothing_is_done_to_yourself(api):
    async with api.as_("root") as http:
        for response in (
            await http.post("/api/admin/users/root/deactivate"),
            await http.patch("/api/admin/users/root", json={"is_superadmin": False}),
            await http.patch("/api/admin/users/root", json={"name": "Me"}),
            await http.delete("/api/admin/users/root?confirm=root@example.com"),
        ):
            assert response.status_code in (400, 409), response.text
        plan = (await http.get("/api/admin/users/root/deletion")).json()
    assert plan["blocked"].startswith("You cannot do this to your own account")
    assert _phases(api.audit, "suspend_user") == []


@pytest.mark.asyncio
async def test_the_last_active_platform_admin_is_never_taken_away(api, team):
    """Someone a policy lets manage accounts, who is no platform admin, still cannot
    deactivate, demote or delete the only one."""
    _operator(
        team,
        [
            "nexus:SuspendUser",
            "nexus:UpdateUser",
            "nexus:DeleteUser",
            "iam:SuspendPrincipal",
            "iam:DeletePrincipal",
        ],
    )
    async with api.as_("operator") as http:
        off = await http.post("/api/admin/users/root/deactivate")
        assert off.status_code == 400
        assert "at least one active platform admin" in off.json()["detail"]
        demoted = await http.patch("/api/admin/users/root", json={"is_superadmin": False})
        assert demoted.status_code == 400
        plan = (await http.get("/api/admin/users/root/deletion")).json()
        assert "at least one active platform admin" in plan["blocked"]
    assert _status(team, "root") == "active"


@pytest.mark.asyncio
async def test_iam_decides_the_change_inside_and_a_refusal_changes_nothing(api, team):
    """The route's action is not enough: IAM's own (``iam:SuspendPrincipal``) is asked as
    the caller, and its refusal is audited and leaves the account as it was."""
    _operator(team, ["nexus:SuspendUser"])
    async with api.as_("operator") as http:
        refused = await http.post("/api/admin/users/member/deactivate")
    assert refused.status_code == 403, refused.text
    assert _status(team, "member") == "active"
    assert not api.idp.people["member@example.com"].disabled
    assert _phases(api.audit, "suspend_user") == ["requested", "failed"]


# -- editing ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_and_superadmin(api, team):
    async with api.as_("root") as http:
        renamed = await http.patch("/api/admin/users/member", json={"name": "Mia Member"})
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "Mia Member"
        # Sign-in refreshes the name from the provider: it is renamed there too.
        assert api.idp.people["member@example.com"].name == "Mia Member"
        promoted = await http.patch("/api/admin/users/member", json={"is_superadmin": True})
        assert promoted.json()["is_superadmin"] is True
        demoted = await http.patch("/api/admin/users/member", json={"is_superadmin": False})
        assert demoted.json()["is_superadmin"] is False
    assert _phases(api.audit, "grant_platform_admin") == ["requested", "succeeded"]
    assert _phases(api.audit, "rename_user") == ["requested", "succeeded"]


# -- deleting -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_deletion_says_what_goes_and_what_stays(api, team):
    async with api.as_("root") as http:
        plan = (await http.get("/api/admin/users/member/deletion")).json()
    assert plan["blocked"] is None
    goes = plan["goes"]
    assert goes["iam_user"] == team.principal("member")
    assert goes["provider_account"]["provider"] == "builtin"
    assert {(m["label"], m["role"]) for m in goes["memberships"]} == {
        ("Organization Acme", "member"),
        ("Workspace Research", "member"),
    }
    assert goes["attachments"] >= 2 and goes["sessions"] == 1
    assert plan["stays"]["workspaces"] == [{"id": "ws-1", "name": "Research"}]


@pytest.mark.asyncio
async def test_an_organizations_only_owner_is_not_deleted(api):
    async with api.as_("root") as http:
        plan = (await http.get("/api/admin/users/owner/deletion")).json()
        refused = await http.delete("/api/admin/users/owner?confirm=owner@example.com")
    assert "only owner of Organization Acme" in plan["blocked"]
    assert refused.status_code == 409


@pytest.mark.asyncio
async def test_deleting_needs_the_email_and_takes_the_account_away(api, team):
    async with api.as_("root") as http:
        wrong = await http.delete("/api/admin/users/member?confirm=someone@example.com")
        assert wrong.status_code == 400
        assert _status(team, "member") == "active"

        gone = await http.delete("/api/admin/users/member?confirm=MEMBER@example.com")
        assert gone.status_code == 200, gone.text
        ids = {row["id"] for row in (await http.get("/api/admin/users")).json()}
    assert "member" not in ids
    assert _status(team, "member") == "deleted"
    with as_service_account("api"):
        assert team.iam.list_attachments(principal_id=team.principal("member")) == []
    assert "member@example.com" not in api.idp.people
    async with api.db() as db:
        row = await db.get(UserModel, "member")
        # The row stays as the author of what they wrote, its email released.
        assert row.deleted_at is not None and row.email == "member@deleted.internal"
        assert await db.get(AuthSessionModel, "s" * 64) is None
    assert _phases(api.audit, "delete_user") == ["requested", "succeeded"]


# -- the review's cases -------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "status"),
    [
        (ProviderUnavailableError("down"), 502),
        (ProvisioningError("refused"), 502),
        (ValueError("not an address it takes"), 400),
    ],
)
async def test_a_provider_failing_the_invitation_is_answered_not_a_500(api, failure, status):
    api.idp.provision_fails = failure
    async with api.as_("root") as http:
        response = await http.post("/api/admin/users/invite", json={"email": "fay@example.com"})
        ids = {row["id"] for row in (await http.get("/api/admin/users")).json()}
    assert response.status_code == status, response.text
    assert "invited:fay@example.com" not in ids


@pytest.mark.asyncio
async def test_an_invitee_at_a_provider_that_manages_its_people_is_deleted(api):
    """Nothing to delete at the provider: the invitations go, as asked."""
    async with api.as_("root") as http:
        await http.post("/api/admin/users/invite", json={"email": "gus@example.com"})
        api.idp.managed = True
        account = quote("invited:gus@example.com", safe="")
        plan = await http.get(f"/api/admin/users/{account}/deletion")
        assert plan.status_code == 200 and plan.json()["blocked"] is None
        gone = await http.delete(f"/api/admin/users/{account}?confirm=gus@example.com")
        assert gone.status_code == 200, gone.text
        ids = {row["id"] for row in (await http.get("/api/admin/users")).json()}
    assert "invited:gus@example.com" not in ids


@pytest.mark.asyncio
async def test_a_deletion_that_failed_after_iam_finishes_on_retry(api, team):
    """IAM deleted the principal, then retiring the row failed: deleting again retires it."""
    with as_service_account("engine"):
        team.iam.delete_principal(team.principal("member"))
    async with api.as_("root") as http:
        gone = await http.delete("/api/admin/users/member?confirm=member@example.com")
        assert gone.status_code == 200, gone.text
        ids = {row["id"] for row in (await http.get("/api/admin/users")).json()}
    assert "member" not in ids


@pytest.mark.asyncio
async def test_a_provider_that_keeps_the_account_is_said_and_blocks_a_reinvitation(api):
    async with api.as_("root") as http:
        api.idp.managed = True
        plan = (await http.get("/api/admin/users/viewer/deletion")).json()
        assert plan["warning"] is None  # never signed in: no identity to keep
        plan = (await http.get("/api/admin/users/member/deletion")).json()
        assert "keeps their account" in plan["warning"]
        api.idp.managed = False

        api.idp.delete_fails = True
        gone = await http.delete("/api/admin/users/member?confirm=member@example.com")
        assert gone.status_code == 200, gone.text
        assert "keeps their account" in gone.json()["warning"]
        again = await http.post("/api/admin/users/invite", json={"email": "member@example.com"})
    assert again.status_code == 409, again.text
    assert "delete it at the provider first" in again.json()["detail"]


@pytest.mark.asyncio
async def test_a_refused_superadmin_change_leaves_the_name_as_it_was(api, team):
    _operator(team, ["nexus:UpdateUser"])
    async with api.as_("operator") as http:
        refused = await http.patch(
            "/api/admin/users/root", json={"name": "Renamed", "is_superadmin": False}
        )
    assert refused.status_code == 400
    assert "at least one active platform admin" in refused.json()["detail"]
    async with api.db() as db:
        assert (await db.get(UserModel, "root")).name == "Root"
    assert api.idp.people["root@example.com"].name == "Root"
    assert _phases(api.audit, "rename_user") == []
