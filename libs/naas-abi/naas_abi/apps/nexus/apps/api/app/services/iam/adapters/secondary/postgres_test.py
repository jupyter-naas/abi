from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.adapters.secondary import postgres
from naas_abi.apps.nexus.apps.api.app.services.iam.adapters.secondary.postgres import (
    IAMSecondaryAdapterPostgres,
)


def _scalar_result(single=None):
    return SimpleNamespace(
        scalar_one_or_none=lambda: single,
    )


@pytest.mark.asyncio
async def test_role_lookups_delegate_to_the_shared_resolver(monkeypatch) -> None:
    """Role logic (org inheritance included) lives in core.workspace_access."""
    db = AsyncMock()
    calls: list[tuple] = []

    async def fake_workspace_role(session, user_id, workspace_id):
        calls.append(("workspace", session, user_id, workspace_id))
        return "admin"

    async def fake_org_role(session, user_id, org_id):
        calls.append(("organization", session, user_id, org_id))
        return "owner"

    monkeypatch.setattr(postgres, "resolve_workspace_role", fake_workspace_role)
    monkeypatch.setattr(postgres, "resolve_organization_role", fake_org_role)
    adapter = IAMSecondaryAdapterPostgres(db=db)

    assert await adapter.get_workspace_role("user-1", "ws-1") == "admin"
    assert await adapter.get_organization_role("user-1", "org-1") == "owner"
    assert calls == [
        ("workspace", db, "user-1", "ws-1"),
        ("organization", db, "user-1", "org-1"),
    ]


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
