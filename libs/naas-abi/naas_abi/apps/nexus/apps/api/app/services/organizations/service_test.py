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
