from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationPermissionError,
    OrganizationService,
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
