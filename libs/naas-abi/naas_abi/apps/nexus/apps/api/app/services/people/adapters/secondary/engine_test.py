"""The people service on the engine's real IAM and Nexus's tables (SQLite), with the
identity provider in memory (#1589): an organization and workspaces whose people are
groups (#1585), a grant is a level and groups, checked as the inviting person before
the provider is asked, and every join, leave and level change is recorded with who
asked."""

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
from naas_abi.apps.nexus.apps.api.app.services.iam.capabilities import ensure_capability
from naas_abi.apps.nexus.apps.api.app.services.iam.levels import LEVELS
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    GroupChange,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
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
    LastOrgAdminError,
    ProviderInfo,
    Provisioned,
    UserStatus,
    WorkspaceAccess,
)
from naas_abi.apps.nexus.apps.api.app.services.people.service import UNBOUND_PREFIX, PeopleService
from naas_abi.apps.nexus.apps.api.app.services.people.service_test import NOW, Mailer
from naas_abi_core.engine.call_context import as_service_account
from sqlalchemy import select

BUILTIN = ProviderInfo("builtin", "Built-in", "https://idp.test", "builtin")
CORP = ProviderInfo("corp", "Corp", "https://corp.test", "none")
ORG1 = org_container("org-1")
PEOPLE = ("oadmin", "wadmin", "member", "viewer", "stranger")


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


def _by(user: str):
    return SimpleNamespace(id=user, name=user.title())


@pytest.fixture
def grouped():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        org = nexus.grouped_org("org-1", "Acme")
        nexus.ws1 = nexus.grouped_workspace("org-1", "ws-1", "Research")  # type: ignore[attr-defined]
        nexus.ws2 = nexus.grouped_workspace("org-1", "ws-2", "Sales")  # type: ignore[attr-defined]
        for person in PEOPLE:
            nexus.user(person)
        with as_service_account("api"):
            runners = ensure_capability(
                nexus.iam, "org-1", "workflow_runners", org_access=org.access_policy_id
            )
        nexus.runners = runners.group_id  # type: ignore[attr-defined]
        yield nexus


@pytest_asyncio.fixture
async def people(grouped, nexus_db):
    async with nexus_db() as db:
        for user in PEOPLE:
            db.add(
                UserModel(
                    id=user,
                    email=f"{user}@example.com",
                    name=user.title(),
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        db.add(OrganizationModel(id="org-1", name="Acme", slug="acme", owner_id="oadmin"))
        await db.flush()
        for ws, name in (("ws-1", "Research"), ("ws-2", "Sales")):
            db.add(
                WorkspaceModel(
                    id=ws,
                    name=name,
                    slug=name.lower(),
                    owner_id="oadmin",
                    organization_id="org-1",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        await db.commit()
    await MEMBERSHIPS.grant("oadmin", "admin", ORG1)
    await MEMBERSHIPS.grant("wadmin", "admin", grouped.ws1.container)
    await MEMBERSHIPS.grant("member", "member", grouped.ws1.container)
    await MEMBERSHIPS.grant("viewer", "viewer", grouped.ws1.container)
    audit: list[GroupChange] = []

    async def record(change: GroupChange) -> None:
        audit.append(change)

    MEMBERSHIPS.audit_sinks.append(record)
    idp, mailer = Idp(), Mailer()
    sessions = []

    async def open_service() -> PeopleService:
        db = nexus_db()
        sessions.append(db)
        return PeopleService(
            PeopleSecondaryAdapterPostgres(await db.__aenter__()),
            idp,
            EngineAccessGateway(lambda: grouped.iam),
            mailer,
            clock=lambda: NOW,
        )

    yield SimpleNamespace(
        open=open_service, idp=idp, mailer=mailer, db=nexus_db, nexus=grouped, audit=audit
    )
    MEMBERSHIPS.audit_sinks.remove(record)
    for db in sessions:
        await db.__aexit__(None, None, None)


def _members(nexus, group_id) -> set[str]:
    with as_service_account("api"):
        return {
            nexus.iam.get_principal(p).subject or p for p in nexus.iam.list_group_members(group_id)
        }


def _groups_of(nexus, principal_id: str) -> set[str]:
    with as_service_account("api"):
        return {str(g.id) for g in nexus.iam.list_principal_groups(principal_id)}


@pytest.mark.asyncio
async def test_an_org_admin_creates_a_person_in_two_workspaces_admin_of_one(people):
    nexus = people.nexus
    service = await people.open()
    result = await service.create_or_link(
        email="bob@example.com",
        name="Bob",
        provider=None,
        grant=Grant(
            "org-1",
            workspaces=(WorkspaceAccess("ws-1"), WorkspaceAccess("ws-2", admin=True)),
            capabilities=(nexus.runners,),
        ),
        by=_by("oadmin"),
    )

    user = result.user
    assert user.id.startswith("usr_") and user.status == UserStatus.INVITED
    levels = LEVELS.get(nexus.iam)
    assert _groups_of(nexus, user.id) >= {
        nexus.ws1.members_group_id,
        nexus.ws2.members_group_id,
        nexus.ws2.admins_group_id,
        levels.members,
        nexus.runners,
    }
    assert nexus.ws1.admins_group_id not in _groups_of(nexus, user.id)
    assert await MEMBERSHIPS.roles_of(user.id) == {
        nexus.ws1.container: "member",
        nexus.ws2.container: "admin",
    }
    with as_service_account("api"):
        # Nothing is attached to the person: they are their groups.
        assert nexus.iam.list_attachments(principal_id=user.id) == []
        assert nexus.iam.list_pending_grants(email="bob@example.com") == []
    async with people.db() as db:
        row = await db.get(UserModel, user.id)
        assert (row.status, row.principal_id, row.idp_subject) == ("invited", user.id, "sub-bob")
        assert await db.get(ProvisionedIdentityModel, ("builtin", "sub-bob")) is not None
    # Every join names who asked (IAM's own audit names ``api``).
    joins = [c for c in people.audit if c.member_id == user.id]
    assert joins and {c.by for c in joins} == {"oadmin"}


@pytest.mark.asyncio
async def test_what_the_inviter_may_not_give_is_refused_before_the_provider_is_asked(people):
    service = await people.open()
    for by, grant in (
        ("member", Grant("org-1", workspaces=(WorkspaceAccess("ws-1"),))),
        ("wadmin", Grant("org-1", workspaces=(WorkspaceAccess("ws-2"),))),
        ("wadmin", Grant("org-1", org_admin=True)),
    ):
        with pytest.raises(GrantNotHeldError):
            await service.create_or_link(
                email="eve@example.com", name=None, provider=None, grant=grant, by=_by(by)
            )
    assert people.idp.asked == []
    async with people.db() as db:
        found = await db.execute(select(UserModel).where(UserModel.email == "eve@example.com"))
        assert found.first() is None


@pytest.mark.asyncio
async def test_a_workspace_admin_adds_someone_who_exists_and_a_member_is_already_one(people):
    service = await people.open()
    ws1 = people.nexus.ws1
    linked = await service.create_or_link(
        email="Stranger@example.com",
        name=None,
        provider=None,
        grant=Grant("org-1", level="viewer", workspaces=(WorkspaceAccess("ws-1"),)),
        by=_by("wadmin"),
    )
    assert linked.user.id == "stranger" and not linked.created
    assert people.idp.asked == []
    assert await MEMBERSHIPS.roles_of("stranger") == {ws1.container: "viewer"}
    with pytest.raises(AlreadyMemberError):
        await service.add_existing(
            user_id="member",
            grant=Grant("org-1", workspaces=(WorkspaceAccess("ws-1"),)),
            by=_by("wadmin"),
        )


@pytest.mark.asyncio
async def test_a_workspace_admin_changes_a_level_everywhere_audited_and_a_member_may_not(people):
    service = await people.open()
    nexus = people.nexus
    await MEMBERSHIPS.grant("viewer", "viewer", nexus.ws2.container)
    people.audit.clear()

    before = await service.set_level(user_id="viewer", level="member", by=_by("wadmin"))

    assert before == "viewer"
    assert await MEMBERSHIPS.level_of("viewer") == "member"
    # One level, everywhere: Sales too, where wadmin administers nothing.
    assert await MEMBERSHIPS.role_at("viewer", nexus.ws2.container) == "member"
    levels = LEVELS.get(nexus.iam)
    assert {(c.action, c.group_id, c.by) for c in people.audit} == {
        ("iam:AddGroupMember", levels.members, "wadmin"),
        ("iam:RemoveGroupMember", levels.viewers, "wadmin"),
    }
    with pytest.raises(GrantNotHeldError):
        await service.set_level(user_id="viewer", level="viewer", by=_by("member"))
    assert await MEMBERSHIPS.level_of("viewer") == "member"


@pytest.mark.asyncio
async def test_an_org_only_person_joins_the_organizations_people(people):
    service = await people.open()
    result = await service.create_or_link(
        email="fay@example.com",
        name=None,
        provider=None,
        grant=Grant("org-1", level="viewer"),
        by=_by("oadmin"),
        profile={"job_title": "CFO"},
    )
    roles = await MEMBERSHIPS.roles_of(result.user.id)
    assert roles == {ORG1: "viewer"}
    directory = {e.user_id: e for e in await MEMBERSHIPS.org_directory("org-1")}
    assert directory[result.user.id].source == "organization"


@pytest.mark.asyncio
async def test_change_access_and_the_last_org_admin(people):
    service = await people.open()
    nexus = people.nexus
    await service.change_access(
        user_id="member",
        organization_id="org-1",
        by=_by("oadmin"),
        workspaces=[WorkspaceAccess("ws-2", admin=True)],
        among=["ws-1", "ws-2"],
        capabilities=[nexus.runners],
    )
    assert await MEMBERSHIPS.roles_of("member") == {nexus.ws2.container: "admin"}
    assert nexus.runners in _groups_of(nexus, await MEMBERSHIPS.principal_id("member"))
    with pytest.raises(LastOrgAdminError):
        await service.change_access(
            user_id="oadmin", organization_id="org-1", by=_by("oadmin"), org_admin=False
        )


@pytest.mark.asyncio
async def test_the_capability_groups_are_the_organizations_own(people):
    gateway = EngineAccessGateway(lambda: people.nexus.iam)
    found = await gateway.capability_groups("org-1")
    assert found == [(people.nexus.runners, "Workflow runners")]


@pytest.mark.asyncio
async def test_a_provider_managing_its_people_leaves_an_unbound_row_in_its_groups(people):
    service = await people.open()
    result = await service.create_or_link(
        email="dan@corp.test",
        name="Dan",
        provider="corp",
        grant=Grant("org-1", workspaces=(WorkspaceAccess("ws-1"),)),
        by=_by("wadmin"),
    )
    user = result.user
    assert user.id.startswith(UNBOUND_PREFIX) and user.provider == "corp"
    assert await MEMBERSHIPS.roles_of(user.id) == {people.nexus.ws1.container: "member"}
    async with people.db() as db:
        row = await db.get(UserModel, user.id)
        assert (row.principal_id, row.idp_issuer, row.status) == (None, None, "invited")


@pytest.mark.asyncio
async def test_search_matches_name_or_email_among_the_ids_given(people):
    service = await people.open()
    among = {"oadmin", "wadmin", "member", "viewer"}
    assert [u.id for u in await service.search(q="WADM", among=among)] == ["wadmin"]
    assert await service.search(q="stranger", among=among) == []
    assert await service.search(q="%", among=among) == []
