from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationDomainAlreadyExistsError,
    OrganizationMemberAlreadyExistsError,
    OrganizationPermissionError,
    OrganizationService,
    OrganizationSlugAlreadyExistsError,
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
