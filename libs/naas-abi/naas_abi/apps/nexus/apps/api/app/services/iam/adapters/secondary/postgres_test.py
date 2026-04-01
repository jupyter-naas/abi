from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.adapters.secondary.postgres import (
    IAMSecondaryAdapterPostgres,
)


def _scalar_result(single=None):
    return SimpleNamespace(
        scalar_one_or_none=lambda: single,
    )


@pytest.mark.asyncio
async def test_get_workspace_role_returns_member_role() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(single="member"),
        ]
    )
    adapter = IAMSecondaryAdapterPostgres(db=db)

    role = await adapter.get_workspace_role("user-1", "ws-1")

    assert role == "member"


@pytest.mark.asyncio
async def test_get_workspace_role_returns_owner_fallback() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(single=None),
            _scalar_result(single="user-1"),
        ]
    )
    adapter = IAMSecondaryAdapterPostgres(db=db)

    role = await adapter.get_workspace_role("user-1", "ws-1")

    assert role == "owner"


@pytest.mark.asyncio
async def test_get_workspace_role_returns_none_when_missing() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(single=None),
            _scalar_result(single="user-2"),
        ]
    )
    adapter = IAMSecondaryAdapterPostgres(db=db)

    role = await adapter.get_workspace_role("user-1", "ws-1")

    assert role is None


@pytest.mark.asyncio
async def test_get_organization_role_returns_member_role() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(single="admin"),
        ]
    )
    adapter = IAMSecondaryAdapterPostgres(db=db)

    role = await adapter.get_organization_role("user-1", "org-1")

    assert role == "admin"


@pytest.mark.asyncio
async def test_get_conversation_access_record_maps_row() -> None:
    row = SimpleNamespace(
        id="conv-1",
        workspace_id="ws-1",
        user_id="user-1",
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=row))
    adapter = IAMSecondaryAdapterPostgres(db=db)

    record = await adapter.get_conversation_access_record("conv-1")

    assert record is not None
    assert record.conversation_id == "conv-1"
    assert record.workspace_id == "ws-1"
    assert record.owner_user_id == "user-1"


@pytest.mark.asyncio
async def test_get_conversation_access_record_returns_none_when_missing() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=None))
    adapter = IAMSecondaryAdapterPostgres(db=db)

    record = await adapter.get_conversation_access_record("conv-missing")

    assert record is None
