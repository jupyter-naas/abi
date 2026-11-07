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
    OrganizationMemberAlreadyExistsError,
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
async def test_invite_member_raises_when_member_exists(team) -> None:
    adapter = SimpleNamespace(
        get_user_by_email=AsyncMock(
            return_value=SimpleNamespace(id="viewer", email="v@x.io", name="V")
        ),
    )
    service = OrganizationService(adapter=adapter)

    with pytest.raises(OrganizationMemberAlreadyExistsError):
        await service.invite_member(
            org_id="org-1",
            email="user@example.com",
            role="member",
            now=datetime.utcnow(),
            by="admin",
        )


@pytest.mark.asyncio
async def test_add_domain_raises_when_domain_exists() -> None:
    adapter = SimpleNamespace(domain_exists=AsyncMock(return_value=True))
    service = OrganizationService(adapter=adapter)

    with pytest.raises(OrganizationDomainAlreadyExistsError):
        await service.add_domain(
            org_id="org-1",
            domain="example.com",
            now=datetime.utcnow(),
            verification_token="token",
        )


@pytest.mark.asyncio
async def test_list_all_workspaces_delegates_to_adapter() -> None:
    rows = [SimpleNamespace(id="ws-1")]
    adapter = SimpleNamespace(list_workspaces_for_org=AsyncMock(return_value=rows))
    service = OrganizationService(adapter=adapter)

    result = await service.list_all_workspaces(org_id="org-1")

    assert result == rows
    adapter.list_workspaces_for_org.assert_awaited_once_with(org_id="org-1")


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
        list_organization_member_profiles=AsyncMock(
            return_value={
                "member": OrganizationMemberProfileRecord(
                    name="Ignored", job_title="CTO", organization="Acme", bio=None
                )
            }
        ),
    )
    service = OrganizationService(adapter=adapter)

    member = await service.get_organization_member("org-1", "member")

    assert member is not None
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
