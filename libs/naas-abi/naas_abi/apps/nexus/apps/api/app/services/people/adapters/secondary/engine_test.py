"""The people service on the engine's real IAM and Nexus's tables (SQLite), with the
identity provider in memory: what IAM refuses is refused before the provider is
asked, what it accepts is attached to the new principal, and the rows are as the
sign-in expects them."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    ProvisionedIdentityModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from naas_abi.apps.nexus.apps.api.app.services.people.adapters.secondary.engine import (
    EngineAccessGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.people.adapters.secondary.postgres import (
    PeopleSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    AlreadyMemberError,
    Grant,
    GrantNotHeldError,
    IdentityGateway,
    OwnerGrantRefusedError,
    ProviderInfo,
    Provisioned,
    UserStatus,
)
from naas_abi.apps.nexus.apps.api.app.services.people.service import UNBOUND_PREFIX, PeopleService
from naas_abi.apps.nexus.apps.api.app.services.people.service_test import NOW, Mailer
from naas_abi_core.engine.call_context import as_service_account
from sqlalchemy import select

BUILTIN = ProviderInfo("builtin", "Built-in", "https://idp.test", "builtin")
CORP = ProviderInfo("corp", "Corp", "https://corp.test", "none")
WS1 = workspace_container("org-1", "ws-1")
ORG1 = org_container("org-1")


class Idp(IdentityGateway):
    def __init__(self) -> None:
        self.accounts: dict[str, str] = {}
        self.asked: list[str] = []
        self.deleted: list[str] = []

    async def providers(self):
        return [BUILTIN, CORP], "builtin"

    async def provision(self, provider, email, name, *, by=None):
        self.asked.append(email)
        if provider.managed_in_provider:
            return None
        created = email not in self.accounts
        self.accounts.setdefault(email, f"sub-{email.split('@')[0]}")
        return Provisioned(self.accounts[email], created)

    async def delete(self, provider, subject):
        self.deleted.append(subject)


@pytest_asyncio.fixture
async def people(team, nexus_db):
    async with nexus_db() as db:
        for user in ("owner", "admin", "member", "viewer", "stranger"):
            db.add(
                UserModel(
                    id=user,
                    email=f"{user}@example.com",
                    name=user.title(),
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
        await db.commit()
    idp, mailer = Idp(), Mailer()
    sessions = []

    def service(db) -> PeopleService:
        return PeopleService(
            PeopleSecondaryAdapterPostgres(db),
            idp,
            EngineAccessGateway(lambda: team.iam),
            mailer,
            clock=lambda: NOW,
        )

    async def open_service() -> PeopleService:
        db = nexus_db()
        sessions.append(db)
        return service(await db.__aenter__())

    yield SimpleNamespace(open=open_service, idp=idp, mailer=mailer, db=nexus_db, team=team)
    for db in sessions:
        await db.__aexit__(None, None, None)


def _by(user: str):
    return SimpleNamespace(id=user, name=user.title())


@pytest.mark.asyncio
async def test_a_workspace_admin_creates_an_invited_member_with_iam_principal(people):
    service = await people.open()
    result = await service.create_or_link(
        email="bob@example.com",
        name="Bob",
        provider=None,
        grants=[Grant("workspace", "ws-1", "member")],
        by=_by("admin"),
    )

    user = result.user
    assert user.id.startswith("usr_") and user.status == UserStatus.INVITED
    assert await MEMBERSHIPS.roles_of(user.id) == {WS1: "member"}
    with as_service_account("api"):
        record = people.team.iam.get_principal(user.id)
        assert (record.issuer, record.subject) == ("https://idp.test", "sub-bob")
        # The warrant is spent: nothing waits to be claimed.
        assert people.team.iam.list_pending_grants(email="bob@example.com") == []
    async with people.db() as db:
        row = await db.get(UserModel, user.id)
        assert (row.status, row.principal_id, row.idp_subject) == ("invited", user.id, "sub-bob")
        assert await db.get(ProvisionedIdentityModel, ("builtin", "sub-bob")) is not None
    assert [m[0] for m in people.mailer.invitations] == ["bob@example.com"]


@pytest.mark.asyncio
async def test_what_the_inviter_does_not_hold_is_refused_before_the_provider_is_asked(people):
    service = await people.open()
    with pytest.raises(GrantNotHeldError):
        await service.create_or_link(
            email="eve@example.com",
            name=None,
            provider=None,
            grants=[Grant("workspace", "ws-1", "admin")],
            by=_by("member"),
        )
    with pytest.raises(OwnerGrantRefusedError):
        await service.create_or_link(
            email="eve@example.com",
            name=None,
            provider=None,
            grants=[Grant("workspace", "ws-1", "owner")],
            by=_by("admin"),
        )
    assert people.idp.asked == []
    async with people.db() as db:
        found = await db.execute(select(UserModel).where(UserModel.email == "eve@example.com"))
        assert found.first() is None
    with as_service_account("api"):
        assert people.team.iam.list_pending_grants(email="eve@example.com") == []


@pytest.mark.asyncio
async def test_an_existing_account_is_linked_and_a_member_is_already_one(people):
    service = await people.open()
    linked = await service.create_or_link(
        email="Stranger@example.com",
        name=None,
        provider=None,
        grants=[Grant("workspace", "ws-1", "viewer")],
        by=_by("admin"),
    )
    assert linked.user.id == "stranger" and not linked.created
    assert people.idp.asked == []
    assert (await MEMBERSHIPS.roles_of("stranger")) == {WS1: "viewer"}
    with pytest.raises(AlreadyMemberError):
        await service.add_existing(
            user_id="member", grants=[Grant("workspace", "ws-1", "viewer")], by=_by("admin")
        )


@pytest.mark.asyncio
async def test_a_provider_managing_its_people_leaves_an_unbound_row_holding_its_roles(people):
    service = await people.open()
    result = await service.create_or_link(
        email="dan@corp.test",
        name="Dan",
        provider="corp",
        grants=[Grant("workspace", "ws-1", "member")],
        by=_by("admin"),
    )
    user = result.user
    assert user.id.startswith(UNBOUND_PREFIX) and user.provider == "corp"
    # IAM's user of the row's id holds the role; the sign-in at corp binds it.
    assert await MEMBERSHIPS.roles_of(user.id) == {WS1: "member"}
    async with people.db() as db:
        row = await db.get(UserModel, user.id)
        assert (row.principal_id, row.idp_issuer, row.status) == (None, None, "invited")


@pytest.mark.asyncio
async def test_an_org_admin_makes_an_org_admin_who_reaches_its_workspaces(people):
    service = await people.open()
    result = await service.create_or_link(
        email="fay@example.com",
        name=None,
        provider=None,
        grants=[Grant("organization", "org-1", "admin")],
        by=_by("owner"),
        organization_id="org-1",
        profile={"job_title": "CFO"},
    )
    roles = await MEMBERSHIPS.roles_of(result.user.id)
    assert roles[ORG1] == "admin" and roles[f"{ORG1}/*"] == "admin"


@pytest.mark.asyncio
async def test_search_matches_name_or_email_among_the_ids_given(people):
    service = await people.open()
    among = {"owner", "admin", "member", "viewer"}
    assert [u.id for u in await service.search(q="ADM", among=among)] == ["admin"]
    assert [u.id for u in await service.search(q="example", among=among, limit=2)] == [
        "admin",
        "member",
    ]
    assert await service.search(q="stranger", among=among) == []
    assert await service.search(q="%", among=among) == []
    assert await service.search(q="a", among=among) == []
