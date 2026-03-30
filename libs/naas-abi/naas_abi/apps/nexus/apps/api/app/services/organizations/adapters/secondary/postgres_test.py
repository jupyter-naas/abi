from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)


def _scalar_result(single=None):
    return SimpleNamespace(
        scalar_one_or_none=lambda: single,
    )


@pytest.mark.asyncio
async def test_get_organization_role_returns_member_role() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(single="admin"),
        ]
    )
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    role = await adapter.get_organization_role("user-1", "org-1")

    assert role == "admin"


@pytest.mark.asyncio
async def test_get_organization_role_returns_owner_fallback() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(single=None),
            _scalar_result(single="user-1"),
        ]
    )
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    role = await adapter.get_organization_role("user-1", "org-1")

    assert role == "owner"


@pytest.mark.asyncio
async def test_get_organization_role_returns_none_when_missing() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(single=None),
            _scalar_result(single="user-2"),
        ]
    )
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    role = await adapter.get_organization_role("user-1", "org-1")

    assert role is None
