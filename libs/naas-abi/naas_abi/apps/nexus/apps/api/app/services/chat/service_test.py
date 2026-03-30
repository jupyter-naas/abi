from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.chat.chat__schema import (
    ChatInputMessage,
    CompleteChatInput,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.port import ChatConversationRecord
from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService, ResolvedProvider
from naas_abi.apps.nexus.apps.api.app.services.iam.port import (
    RequestContext,
    TokenData,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMPermissionError


def _conversation(now: datetime) -> ChatConversationRecord:
    return ChatConversationRecord(
        id="conv-1",
        workspace_id="ws-1",
        user_id="user-1",
        title="Title",
        agent="aia",
        created_at=now,
        updated_at=now,
    )


def _context(user_id: str = "user-1") -> RequestContext:
    return RequestContext(
        token_data=TokenData(user_id=user_id, scopes=set(), is_authenticated=True)
    )


@pytest.mark.asyncio
async def test_list_conversations_delegates_to_adapter() -> None:
    adapter = SimpleNamespace(
        list_conversations_by_workspace=AsyncMock(return_value=[]),
    )
    service = ChatService(adapter=adapter)

    result = await service.list_conversations(
        context=_context(),
        workspace_id="ws-1",
        limit=10,
        offset=5,
    )

    assert result == []
    adapter.list_conversations_by_workspace.assert_awaited_once_with(
        workspace_id="ws-1",
        user_id="user-1",
        limit=10,
        offset=5,
    )


@pytest.mark.asyncio
async def test_get_or_create_conversation_updates_agent_for_existing_thread() -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(
            return_value=ChatConversationRecord(
                id="conv-1",
                workspace_id="ws-1",
                user_id="user-1",
                title="Title",
                agent="aia",
                created_at=now,
                updated_at=now,
            )
        ),
        get_conversation_by_id=AsyncMock(),
        update_conversation_agent=AsyncMock(),
    )
    service = ChatService(adapter=adapter)

    conversation_id = await service.get_or_create_conversation(
        conversation_id="conv-1",
        workspace_id="ws-1",
        context=_context(),
        request_message="hello",
        agent="bob",
        now=now,
    )

    assert conversation_id == "conv-1"
    adapter.update_conversation_agent.assert_awaited_once_with(
        conversation_id="conv-1",
        agent="bob",
        now=now,
    )


@pytest.mark.asyncio
async def test_get_or_create_conversation_requires_workspace_when_creating() -> None:
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(return_value=None),
        get_conversation_by_id=AsyncMock(return_value=None),
    )
    service = ChatService(adapter=adapter)

    with pytest.raises(ValueError, match="workspace_id is required"):
        await service.get_or_create_conversation(
            conversation_id=None,
            workspace_id=None,
            context=_context(),
            request_message="hello",
            agent="aia",
            now=datetime.now(),
        )


@pytest.mark.asyncio
async def test_create_message_generates_message_id_and_delegates() -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(return_value=_conversation(now)),
        create_message=AsyncMock(),
    )
    service = ChatService(adapter=adapter)

    message_id = await service.create_message(
        context=_context(),
        conversation_id="conv-1",
        role="user",
        content="Hi",
        created_at=now,
    )

    assert message_id.startswith("msg-")
    adapter.create_message.assert_awaited_once_with(
        message_id=message_id,
        conversation_id="conv-1",
        role="user",
        content="Hi",
        agent=None,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_delete_conversation_with_messages_deletes_messages_first() -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(return_value=_conversation(now)),
        delete_messages_by_conversation=AsyncMock(),
        delete_conversation=AsyncMock(return_value=True),
    )
    service = ChatService(adapter=adapter)

    deleted = await service.delete_conversation_with_messages(
        context=_context(),
        conversation_id="conv-1",
    )

    assert deleted is True
    assert adapter.delete_messages_by_conversation.await_count == 1
    assert adapter.delete_conversation.await_count == 1


@pytest.mark.asyncio
async def test_create_streaming_message_pair_creates_user_then_assistant() -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(return_value=_conversation(now)),
        create_message=AsyncMock(),
    )
    service = ChatService(adapter=adapter)

    user_msg_id, assistant_msg_id = await service.create_streaming_message_pair(
        context=_context(),
        conversation_id="conv-1",
        user_content="hello",
        assistant_agent="aia",
        created_at=now,
    )

    assert user_msg_id.startswith("msg-")
    assert assistant_msg_id.startswith("msg-")
    assert adapter.create_message.await_count == 2


@pytest.mark.asyncio
async def test_finalize_streaming_response_updates_message_and_touches_conversation() -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(return_value=_conversation(now)),
        update_message_content=AsyncMock(return_value=True),
        touch_conversation=AsyncMock(),
    )
    service = ChatService(adapter=adapter)

    await service.finalize_streaming_response(
        context=_context(),
        conversation_id="conv-1",
        assistant_message_id="msg-1",
        content="final answer",
        now=now,
    )

    adapter.update_message_content.assert_awaited_once_with("msg-1", "final answer")
    adapter.touch_conversation.assert_awaited_once_with("conv-1", now)


@pytest.mark.asyncio
async def test_get_or_create_conversation_rejects_other_user_conversation() -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(return_value=None),
        get_conversation_by_id=AsyncMock(
            return_value=ChatConversationRecord(
                id="conv-1",
                workspace_id="ws-1",
                user_id="user-2",
                title="Title",
                agent="aia",
                created_at=now,
                updated_at=now,
            )
        ),
    )
    service = ChatService(adapter=adapter)

    with pytest.raises(PermissionError, match="Conversation not found"):
        await service.get_or_create_conversation(
            conversation_id="conv-1",
            workspace_id="ws-1",
            context=_context(),
            request_message="hello",
            agent="aia",
            now=now,
        )


@pytest.mark.asyncio
async def test_list_messages_denies_when_scope_missing() -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(
            return_value=ChatConversationRecord(
                id="conv-1",
                workspace_id="ws-1",
                user_id="user-1",
                title="Title",
                agent="aia",
                created_at=now,
                updated_at=now,
            )
        ),
    )
    iam_service = SimpleNamespace(
        ensure=lambda *args, **kwargs: (_ for _ in ()).throw(
            IAMPermissionError(scope="chat.message.read")
        )
    )
    service = ChatService(adapter=adapter, iam_service=iam_service)

    with pytest.raises(PermissionError, match="Conversation access denied"):
        await service.list_messages(context=_context(), conversation_id="conv-1")


@pytest.mark.asyncio
async def test_complete_chat_request_without_provider_returns_fallback() -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(return_value=_conversation(now)),
        create_message=AsyncMock(),
        touch_conversation=AsyncMock(),
    )
    service = ChatService(adapter=adapter)
    service.get_or_create_conversation = AsyncMock(return_value="conv-1")
    service.resolve_provider = AsyncMock(return_value=None)

    result = await service.complete_chat_request(
        request=CompleteChatInput(
            message="hello",
            agent="aia",
            workspace_id="ws-1",
        ),
        context=_context(),
        now=now,
    )

    assert result.conversation_id == "conv-1"
    assert result.provider_used is None
    assert "No AI provider available" in result.assistant_content
    assert adapter.create_message.await_count == 2
    adapter.touch_conversation.assert_awaited_once_with("conv-1", now)


@pytest.mark.asyncio
async def test_complete_chat_request_with_provider_uses_completion(monkeypatch) -> None:
    now = datetime.now()
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(return_value=_conversation(now)),
        create_message=AsyncMock(),
        touch_conversation=AsyncMock(),
    )
    service = ChatService(adapter=adapter)
    service.get_or_create_conversation = AsyncMock(return_value="conv-1")
    service.resolve_provider = AsyncMock(
        return_value=ResolvedProvider(
            id="p1",
            name="OpenAI",
            type="openai",
            enabled=True,
            endpoint="https://api.openai.com/v1",
            api_key="k",
            account_id=None,
            model="gpt-4o-mini",
        )
    )
    service.build_provider_messages_with_agents = AsyncMock(
        return_value=[ChatInputMessage(role="user", content="hello")]
    )

    async def _fake_complete_chat(messages, config, system_prompt):
        return '{"content":"assistant answer"}'

    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.chat.service.complete_with_provider",
        _fake_complete_chat,
    )

    result = await service.complete_chat_request(
        request=CompleteChatInput(
            message="hello",
            agent="aia",
            workspace_id="ws-1",
            messages=[ChatInputMessage(role="user", content="hello")],
        ),
        context=_context(),
        now=now,
    )

    assert result.provider_used == "OpenAI (gpt-4o-mini)"
    assert result.assistant_content == "assistant answer"
