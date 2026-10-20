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
    OrganizationRoleNotAssignableError,
    OrganizationService,
    OrganizationSlugAlreadyExistsError,
    member_workspace_access,
)


@pytest.mark.asyncio
async def test_get_organization_role_delegates_to_adapter() -> None:
    adapter = SimpleNamespace(get_organization_role=AsyncMock(return_value="member"))
    service = OrganizationService(adapter=adapter)

    role = await service.get_organization_role(user_id="user-1", org_id="org-1")

    assert role == "member"
    adapter.get_organization_role.assert_awaited_once_with(user_id="user-1", org_id="org-1")


@pytest.mark.asyncio
async def test_require_organization_access_raises_when_missing_role() -> None:
    adapter = SimpleNamespace(get_organization_role=AsyncMock(return_value=None))
    service = OrganizationService(adapter=adapter)

    with pytest.raises(OrganizationPermissionError):
        await service.require_organization_access(user_id="user-1", org_id="org-1")


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
async def test_invite_member_raises_when_member_exists() -> None:
    adapter = SimpleNamespace(
        get_user_by_email=AsyncMock(return_value=SimpleNamespace(id="user-2")),
        is_organization_member=AsyncMock(return_value=True),
    )
    service = OrganizationService(adapter=adapter)

    with pytest.raises(OrganizationMemberAlreadyExistsError):
        await service.invite_member(
            org_id="org-1",
            email="user@example.com",
            role="member",
            now=datetime.utcnow(),
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
async def test_list_workspace_memberships_delegates_to_adapter() -> None:
    rows = [SimpleNamespace(user_id="u1", workspace_id="ws-1", role="member")]
    adapter = SimpleNamespace(
        list_workspace_memberships_for_org=AsyncMock(return_value=rows)
    )
    service = OrganizationService(adapter=adapter)

    result = await service.list_workspace_memberships(org_id="org-1")

    assert result == rows
    adapter.list_workspace_memberships_for_org.assert_awaited_once_with(org_id="org-1")


@pytest.mark.asyncio
async def test_invite_member_refuses_owner_role() -> None:
    """Owners come from the config only: no invite path may create one."""
    adapter = SimpleNamespace(
        get_user_by_email=AsyncMock(return_value=SimpleNamespace(id="user-2")),
        is_organization_member=AsyncMock(return_value=False),
        add_organization_member=AsyncMock(),
    )
    service = OrganizationService(adapter=adapter)

    with pytest.raises(OrganizationRoleNotAssignableError):
        await service.invite_member(
            org_id="org-1",
            email="user@example.com",
            role="owner",
            now=datetime.utcnow(),
        )
    adapter.add_organization_member.assert_not_called()


@pytest.mark.asyncio
async def test_update_member_role_refuses_owner_role() -> None:
    adapter = SimpleNamespace(update_organization_member_role=AsyncMock())
    service = OrganizationService(adapter=adapter)

    with pytest.raises(OrganizationRoleNotAssignableError):
        await service.update_member_role(org_id="org-1", user_id="user-2", role="owner")
    adapter.update_organization_member_role.assert_not_called()


def _ws(ws_id: str, owner_id: str = "someone") -> SimpleNamespace:
    return SimpleNamespace(id=ws_id, name=ws_id.upper(), slug=ws_id, owner_id=owner_id)


def test_member_workspace_access_lists_explicit_memberships() -> None:
    access = member_workspace_access(
        user_id="u1",
        organization_role="member",
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
        organization_role="admin",
        workspaces=[_ws("a"), _ws("b", owner_id="u1")],
        memberships=[
            OrganizationWorkspaceMembershipRecord(user_id="u1", workspace_id="a", role="member"),
        ],
    )

    assert [(a.workspace_id, a.role, a.source) for a in access] == [
        ("a", "admin", "organization"),
        ("b", "owner", "workspace"),
    ]
