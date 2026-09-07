from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.models import OrganizationRoleFeaturesModel
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


@pytest.mark.asyncio
async def test_get_organization_role_features_decodes_json() -> None:
    row = OrganizationRoleFeaturesModel(
        organization_id="org-1",
        role_baseline='{"member":["chat","files"],"viewer":["chat"]}',
        updated_by="user-1",
        created_at=datetime(2026, 7, 30),
        updated_at=datetime(2026, 7, 30),
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=row))
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    record = await adapter.get_organization_role_features("org-1")

    assert record is not None
    assert record.organization_id == "org-1"
    assert record.role_baseline["member"] == ["chat", "files"]
    assert record.updated_by == "user-1"


@pytest.mark.asyncio
async def test_upsert_organization_role_features_inserts_when_missing() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=None))
    db.add = AsyncMock()
    db.flush = AsyncMock()
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    now = datetime(2026, 7, 30, 12, 0, 0)

    record = await adapter.upsert_organization_role_features(
        org_id="org-1",
        role_baseline={
            "owner": ["chat"],
            "admin": ["chat"],
            "member": ["chat"],
            "viewer": ["chat"],
        },
        updated_by="user-1",
        now=now,
    )

    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    assert record.organization_id == "org-1"
    assert record.role_baseline["member"] == ["chat"]
    assert record.updated_by == "user-1"


@pytest.mark.asyncio
async def test_upsert_organization_role_features_updates_existing_row() -> None:
    existing = OrganizationRoleFeaturesModel(
        organization_id="org-1",
        role_baseline='{"member":["chat"]}',
        updated_by="user-0",
        created_at=datetime(2026, 7, 1),
        updated_at=datetime(2026, 7, 1),
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=existing))
    db.flush = AsyncMock()
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    now = datetime(2026, 7, 30, 12, 0, 0)

    record = await adapter.upsert_organization_role_features(
        org_id="org-1",
        role_baseline={
            "owner": ["chat", "files"],
            "admin": ["chat", "files"],
            "member": ["chat", "files"],
            "viewer": ["chat"],
        },
        updated_by="user-1",
        now=now,
    )

    assert existing.updated_by == "user-1"
    assert existing.updated_at == now
    assert '"files"' in existing.role_baseline
    assert record.role_baseline["member"] == ["chat", "files"]
    db.flush.assert_awaited_once()
