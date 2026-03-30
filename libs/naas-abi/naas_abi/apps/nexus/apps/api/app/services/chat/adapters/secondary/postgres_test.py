from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.postgres import (
    ChatSecondaryAdapterPostgres,
)


def _scalar_result(single=None, many=None):
    scalars = SimpleNamespace(
        all=lambda: many or [],
    )
    return SimpleNamespace(
        scalar_one_or_none=lambda: single,
        scalars=lambda: scalars,
    )


@pytest.mark.asyncio
async def test_list_conversations_by_workspace_maps_rows() -> None:
    row = SimpleNamespace(
        id="conv-1",
        workspace_id="ws-1",
        user_id="user-1",
        title="T",
        agent="aia",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        pinned=False,
        archived=False,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(many=[row]))

    adapter = ChatSecondaryAdapterPostgres(db=db)
    conversations = await adapter.list_conversations_by_workspace(
        "ws-1", "user-1", 10, 0
    )

    assert len(conversations) == 1
    assert conversations[0].id == "conv-1"
    assert conversations[0].workspace_id == "ws-1"


@pytest.mark.asyncio
async def test_get_agent_by_id_returns_none_when_missing() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=None))

    adapter = ChatSecondaryAdapterPostgres(db=db)
    agent = await adapter.get_agent_by_id("missing")

    assert agent is None


@pytest.mark.asyncio
async def test_get_conversation_by_id_for_user_maps_row() -> None:
    row = SimpleNamespace(
        id="conv-1",
        workspace_id="ws-1",
        user_id="user-1",
        title="Title",
        agent="aia",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        pinned=False,
        archived=False,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=row))

    adapter = ChatSecondaryAdapterPostgres(db=db)
    conversation = await adapter.get_conversation_by_id_for_user("conv-1", "user-1")

    assert conversation is not None
    assert conversation.id == "conv-1"
    assert conversation.user_id == "user-1"


@pytest.mark.asyncio
async def test_get_agent_by_id_maps_record() -> None:
    row = SimpleNamespace(
        id="agent-1",
        workspace_id="ws-1",
        name="Agent",
        class_name="MyAgent",
        model_id="model-1",
        provider="openai",
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=row))

    adapter = ChatSecondaryAdapterPostgres(db=db)
    agent = await adapter.get_agent_by_id("agent-1")

    assert agent is not None
    assert agent.id == "agent-1"
    assert agent.provider == "openai"


@pytest.mark.asyncio
async def test_delete_conversation_returns_false_when_missing() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=None))

    adapter = ChatSecondaryAdapterPostgres(db=db)
    deleted = await adapter.delete_conversation("conv-1")

    assert deleted is False
    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_conversation_deletes_row_when_found() -> None:
    row = SimpleNamespace(id="conv-1")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=row))

    adapter = ChatSecondaryAdapterPostgres(db=db)
    deleted = await adapter.delete_conversation("conv-1")

    assert deleted is True
    db.delete.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_update_message_content_returns_false_when_missing() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=None))

    adapter = ChatSecondaryAdapterPostgres(db=db)
    updated = await adapter.update_message_content("msg-1", "hello")

    assert updated is False


@pytest.mark.asyncio
async def test_update_message_content_updates_when_found() -> None:
    row = SimpleNamespace(id="msg-1", content="")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(single=row))

    adapter = ChatSecondaryAdapterPostgres(db=db)
    updated = await adapter.update_message_content("msg-1", "hello")

    assert updated is True
    assert row.content == "hello"
    db.flush.assert_awaited_once()
