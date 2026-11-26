from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationWorkspaceMembershipRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationDomainAlreadyExistsError,
    OrganizationPermissionError,
    OrganizationService,
    OrganizationSlugAlreadyExistsError,
    member_workspace_access,
)


@pytest.mark.asyncio
async def test_the_role_is_the_one_iam_holds(team) -> None:
    service = OrganizationService(adapter=SimpleNamespace())

    assert await service.get_organization_role(user_id="admin", org_id="org-1") == "admin"
    assert await service.get_organization_role(user_id="stranger", org_id="org-1") is None


@pytest.mark.asyncio
async def test_require_organization_access_raises_when_missing_role(team) -> None:
    service = OrganizationService(adapter=SimpleNamespace())

    with pytest.raises(OrganizationPermissionError):
        await service.require_organization_access(user_id="stranger", org_id="org-1")


@pytest.mark.asyncio
async def test_create_organization_raises_when_slug_exists() -> None:
    adapter = SimpleNamespace(organization_slug_exists=AsyncMock(return_value=True))
    service = OrganizationService(adapter=adapter)

    with pytest.raises(OrganizationSlugAlreadyExistsError):
        await service.create_organization(
            name="My Org",
            slug="my-org",
            owner_id="user-1",
            now=datetime.utcnow(),
        )


@pytest.mark.asyncio
async def test_add_domain_raises_when_another_organization_verified_it() -> None:
    verified = SimpleNamespace(id="d-1", organization_id="org-2", is_verified=True)
    adapter = SimpleNamespace(get_domain_by_name=AsyncMock(return_value=verified))
    service = OrganizationService(adapter=adapter)

    with pytest.raises(OrganizationDomainAlreadyExistsError):
        await service.add_domain(org_id="org-1", domain="example.com", now=datetime.utcnow())


@pytest.mark.asyncio
async def test_list_all_workspaces_delegates_to_adapter() -> None:
    rows = [SimpleNamespace(id="ws-1")]
    adapter = SimpleNamespace(list_workspaces_for_org=AsyncMock(return_value=rows))
    service = OrganizationService(adapter=adapter)

    result = await service.list_all_workspaces(org_id="org-1")

    assert result == rows
    adapter.list_workspaces_for_org.assert_awaited_once_with(org_id="org-1")


class _CountedMemberships:
    """``MEMBERSHIPS``, counting how often the roles' attachments are read."""

    def __init__(self) -> None:
        from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

        self._memberships = MEMBERSHIPS
        self.passes: list[str] = []

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(self._memberships, name)

    async def members(self, scope: str):  # type: ignore[no-untyped-def]
        self.passes.append("members")
        return await self._memberships.members(scope)

    async def members_of(self, scopes: list[str]):  # type: ignore[no-untyped-def]
        self.passes.append("members_of")
        return await self._memberships.members_of(scopes)


@pytest.mark.asyncio
async def test_every_workspaces_roles_are_read_in_one_pass(team) -> None:
    """#1608: the roles of 60 workspaces in one pass over IAM's role attachments
    (``members_of``), the same rows one read per workspace gave, in the same order."""
    workspaces = [SimpleNamespace(id=f"ws-{i:02d}") for i in range(60)]
    for i, ws in enumerate(workspaces):
        scope = team.workspace("org-1", ws.id)
        team.grant(f"user-{i % 9}", ("admin", "member", "viewer")[i % 3], scope)
    adapter = SimpleNamespace(list_workspaces_for_org=AsyncMock(return_value=workspaces))
    counted = _CountedMemberships()
    service = OrganizationService(adapter=adapter, memberships=counted)  # type: ignore[arg-type]

    batched = await service.list_workspace_memberships(org_id="org-1")
    assert counted.passes == ["members_of"]

    from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container

    one_by_one = [
        (member.user_id, ws.id, member.role)
        for ws in workspaces
        for member in await counted.members(workspace_container("org-1", ws.id))
    ]
    assert [(r.user_id, r.workspace_id, r.role) for r in batched] == one_by_one
    assert len(one_by_one) >= 60


@pytest.mark.asyncio
async def test_one_organizations_roles_name_only_its_people(team, monkeypatch) -> None:
    """Each name is a read: the pass names the holders of the organization asked for, not
    another organization's (as its directory does)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    team.grant("elsewhere", "member", team.workspace("org-9", "ws-9"))
    elsewhere = team.principal("elsewhere")
    named: list[str] = []
    user_id = MEMBERSHIPS._user_id

    def naming(iam, principal_id):  # type: ignore[no-untyped-def]
        named.append(principal_id)
        return user_id(iam, principal_id)

    monkeypatch.setattr(MEMBERSHIPS, "_user_id", naming)
    adapter = SimpleNamespace(
        list_workspaces_for_org=AsyncMock(return_value=[SimpleNamespace(id="ws-1")])
    )
    found = await OrganizationService(adapter=adapter).list_workspace_memberships(org_id="org-1")

    assert {r.user_id for r in found} == {"owner", "admin", "member", "viewer"}
    assert named and elsewhere not in named


@pytest.mark.asyncio
async def test_list_workspace_memberships_reads_each_workspaces_roles(team) -> None:
    adapter = SimpleNamespace(
        list_workspaces_for_org=AsyncMock(return_value=[SimpleNamespace(id="ws-1")])
    )
    service = OrganizationService(adapter=adapter)

    result = await service.list_workspace_memberships(org_id="org-1")

    assert {(r.user_id, r.workspace_id, r.role) for r in result} == {
        ("owner", "ws-1", "owner"),
        ("admin", "ws-1", "admin"),
        ("member", "ws-1", "member"),
        ("viewer", "ws-1", "viewer"),
    }


def _ws(ws_id: str, owner_id: str = "someone") -> SimpleNamespace:
    return SimpleNamespace(id=ws_id, name=ws_id.upper(), slug=ws_id, owner_id=owner_id)


def test_member_workspace_access_lists_explicit_memberships() -> None:
    access = member_workspace_access(
        user_id="u1",
        inherited_role=None,
        workspaces=[_ws("a"), _ws("b"), _ws("c")],
        memberships=[
            OrganizationWorkspaceMembershipRecord(user_id="u1", workspace_id="a", role="viewer"),
            OrganizationWorkspaceMembershipRecord(user_id="u2", workspace_id="b", role="admin"),
        ],
    )

    assert [(a.workspace_id, a.role, a.source) for a in access] == [("a", "viewer", "workspace")]


def test_org_admins_inherit_every_workspace_and_higher_roles_win() -> None:
    access = member_workspace_access(
        user_id="u1",
        inherited_role="admin",
        workspaces=[_ws("a"), _ws("b", owner_id="u1")],
        memberships=[
            OrganizationWorkspaceMembershipRecord(user_id="u1", workspace_id="a", role="member"),
        ],
    )

    assert [(a.workspace_id, a.role, a.source) for a in access] == [
        ("a", "admin", "organization"),
        ("b", "owner", "workspace"),
    ]


@pytest.mark.asyncio
async def test_an_org_owner_and_admin_hold_the_role_in_every_workspace_of_the_org(team) -> None:
    """The organization role is also held below the organization (``<org>/*``) for
    owners and admins; members and viewers inherit nothing. IAM decides, so a
    workspace the user was never added to is theirs to use."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import authz

    team.workspace("org-1", "ws-2")
    adapter = SimpleNamespace(
        get_users_by_ids=AsyncMock(return_value={}),
        list_organization_member_profiles=AsyncMock(return_value={}),
    )
    service = OrganizationService(adapter=adapter)

    assert await service.memberships.inherited_role("admin", "org-1") == "admin"
    assert await service.memberships.inherited_role("owner", "org-1") == "owner"
    assert await service.memberships.inherited_role("member", "org-1") is None
    assert await authz.allowed("UpdateWorkspace", user="admin", workspace="ws-2")
    assert not await authz.allowed("UpdateWorkspace", user="member", workspace="ws-2")

    # Demoted to member: the reach goes with the role.
    await service.update_member_role("org-1", "admin", "member", by="owner")
    assert await service.memberships.inherited_role("admin", "org-1") is None
    assert not await authz.allowed("UpdateWorkspace", user="admin", workspace="ws-2")


@pytest.mark.asyncio
async def test_a_member_shows_the_org_profile_and_the_accounts_name(team) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
        OrganizationMemberProfileRecord,
        UserRecord,
    )

    users = {
        "member": UserRecord(id="member", email="m@x.io", name="Account Name", bio="Account bio")
    }
    adapter = SimpleNamespace(
        get_users_by_ids=AsyncMock(return_value=users),
        get_organization_member_profile=AsyncMock(
            return_value=OrganizationMemberProfileRecord(
                name="Ignored", job_title="CTO", organization="Acme", bio=None
            )
        ),
        list_organization_member_profiles=AsyncMock(side_effect=AssertionError("every profile")),
    )
    service = OrganizationService(adapter=adapter)

    member = await service.get_organization_member("org-1", "member")

    assert member is not None
    # One member is read alone (#1608): their account and their profile, not the directory's.
    adapter.get_users_by_ids.assert_awaited_once_with(["member"])
    adapter.get_organization_member_profile.assert_awaited_once_with("org-1", "member")
    # The name is the account's, the bio falls back to it, the rest is the org's.
    assert (member.name, member.bio) == ("Account Name", "Account bio")
    assert (member.job_title, member.organization, member.avatar) == ("CTO", "Acme", None)


@pytest.mark.asyncio
async def test_every_membership_of_the_platform_is_read_from_iam(team) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.organizations.port import OrganizationRecord

    team.org("org-2")
    team.grant("member", "admin", "abi:nexus:organization/org-2")
    adapter = SimpleNamespace(
        list_all_organizations=AsyncMock(
            return_value=[
                OrganizationRecord(id="org-1", name="Acme", slug="acme", owner_id="owner"),
                OrganizationRecord(id="org-2", name="Beta", slug="beta", owner_id="owner"),
            ]
        )
    )
    service = OrganizationService(adapter=adapter)

    memberships = await service.list_all_memberships()

    assert [(m.user_id, m.organization_name, m.role) for m in memberships] == [
        ("admin", "Acme", "admin"),
        ("member", "Acme", "member"),
        ("member", "Beta", "admin"),
        ("owner", "Acme", "owner"),
        ("viewer", "Acme", "viewer"),
    ]


def _directory_adapter(**extra):
    from naas_abi.apps.nexus.apps.api.app.services.organizations.port import UserRecord

    return SimpleNamespace(
        get_users_by_ids=AsyncMock(
            side_effect=lambda ids: {
                i: UserRecord(id=i, email=f"{i}@x.io", name=i.title(), status="active") for i in ids
            }
        ),
        list_organization_member_profiles=AsyncMock(return_value={}),
        get_organization_member_profile=AsyncMock(return_value=None),
        **extra,
    )


@pytest.mark.asyncio
async def test_the_member_list_is_the_derived_org_directory(team) -> None:
    """Someone given a role only in one of the org's workspaces is listed, with no
    org role: linked to the organization, granted nothing there."""
    team.grant("wsonly", "viewer", team.workspace("org-1", "ws-1"))
    team.grant("elsewhere", "member", team.workspace("org-2", "ws-9"))
    service = OrganizationService(adapter=_directory_adapter())

    members = {m.user_id: m for m in await service.list_members("org-1")}

    assert set(members) == {"owner", "admin", "member", "viewer", "wsonly"}
    assert (members["wsonly"].role, members["wsonly"].source) == (None, "workspace")
    assert (members["admin"].role, members["admin"].source) == ("admin", "organization")
    assert members["wsonly"].status == "active"


@pytest.mark.asyncio
async def test_a_member_is_invited_until_their_first_sign_in(team) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.organizations.port import UserRecord

    adapter = _directory_adapter()
    adapter.get_users_by_ids = AsyncMock(
        side_effect=lambda ids: {
            i: UserRecord(id=i, email=f"{i}@x.io", status="invited" if i == "viewer" else "active")
            for i in ids
        }
    )
    service = OrganizationService(adapter=adapter)

    statuses = {m.user_id: m.status for m in await service.list_members("org-1")}

    assert statuses["viewer"] == "invited" and statuses["owner"] == "active"


@pytest.mark.asyncio
async def test_platform_memberships_include_workspace_only_links(team) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.organizations.port import OrganizationRecord

    team.grant("wsonly", "member", team.workspace("org-1", "ws-2"))
    adapter = SimpleNamespace(
        list_all_organizations=AsyncMock(
            return_value=[OrganizationRecord(id="org-1", name="Acme", slug="acme", owner_id="o")]
        )
    )
    service = OrganizationService(adapter=adapter)

    memberships = {m.user_id: m.role for m in await service.list_all_memberships()}

    assert memberships["wsonly"] is None
    assert memberships["admin"] == "admin"


@pytest.mark.asyncio
async def test_an_org_role_is_given_to_someone_with_workspace_access_only(team) -> None:
    team.grant("wsonly", "viewer", team.workspace("org-1", "ws-1"))
    service = OrganizationService(adapter=_directory_adapter())

    member = await service.update_member_role("org-1", "wsonly", "member", by="admin")

    assert member is not None and (member.role, member.source) == ("member", "organization")
    assert await service.update_member_role("org-1", "stranger", "member", by="admin") is None
