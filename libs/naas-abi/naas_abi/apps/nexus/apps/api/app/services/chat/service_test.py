from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.chat.chat__schema import (
    ChatInputMessage,
    CompleteChatInput,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.port import ChatConversationRecord
from naas_abi.apps.nexus.apps.api.app.services.chat.service import (
    AGENT_SYSTEM_PROMPTS,
    ChatService,
    ResolvedProvider,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import (
    RequestContext,
    TokenData,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMPermissionError
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import Message as ProviderMessage


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
async def test_get_or_create_conversation_creates_new_for_other_user_conversation() -> None:
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
        create_conversation=AsyncMock(
            return_value=ChatConversationRecord(
                id="conv-new",
                workspace_id="ws-1",
                user_id="user-1",
                title="hello",
                agent="aia",
                created_at=now,
                updated_at=now,
            )
        ),
    )
    service = ChatService(adapter=adapter)

    conversation_id = await service.get_or_create_conversation(
        conversation_id="conv-1",
        workspace_id="ws-1",
        context=_context(),
        request_message="hello",
        agent="aia",
        now=now,
    )

    assert conversation_id == "conv-new"
    assert adapter.create_conversation.await_count == 1


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
async def test_get_conversation_for_user_denies_when_scope_missing() -> None:
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(return_value=None),
    )
    iam_service = SimpleNamespace(
        ensure=lambda *args, **kwargs: (_ for _ in ()).throw(
            IAMPermissionError(scope="chat.conversation.read")
        )
    )
    service = ChatService(adapter=adapter, iam_service=iam_service)

    with pytest.raises(PermissionError, match="Conversation access denied"):
        await service.get_conversation_for_user(context=_context(), conversation_id="conv-1")


@pytest.mark.asyncio
async def test_get_workspace_secret_denies_when_scope_missing() -> None:
    adapter = SimpleNamespace(
        get_workspace_secret=AsyncMock(return_value=None),
    )
    iam_service = SimpleNamespace(
        ensure=lambda *args, **kwargs: (_ for _ in ()).throw(
            IAMPermissionError(scope="chat.secret.read")
        )
    )
    service = ChatService(adapter=adapter, iam_service=iam_service)

    with pytest.raises(PermissionError, match="Secret access denied"):
        await service.get_workspace_secret(
            context=_context(),
            workspace_id="ws-1",
            key="OPENAI_API_KEY",
        )


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

    async def _fake_complete_chat(messages, config, system_prompt, thread_id=None):
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


# ---------------------------------------------------------------------------
# Tests: _inject_chat_vector_context (agent retrieval)
# ---------------------------------------------------------------------------

def _make_service_with_no_adapter() -> ChatService:
    return ChatService(adapter=SimpleNamespace())


def _msg(role: str, content: str) -> ProviderMessage:
    return ProviderMessage(role=role, content=content)


def test_inject_returns_unchanged_when_no_conversation_id() -> None:
    service = _make_service_with_no_adapter()
    msgs = [_msg("user", "What is the capital of France?")]
    result, sources = service._inject_chat_vector_context(
        provider_messages=msgs,
        conversation_id=None,
        user_id="u",
        embedding_model="hash-v1",
        embedding_dimension=32,
    )
    assert result == msgs
    assert sources == []


def test_inject_returns_unchanged_when_no_user_message() -> None:
    service = _make_service_with_no_adapter()
    msgs = [_msg("system", "You are an assistant.")]
    result, sources = service._inject_chat_vector_context(
        provider_messages=msgs,
        conversation_id="conv-1",
        user_id="u",
        embedding_model="hash-v1",
        embedding_dimension=32,
    )
    assert result == msgs
    assert sources == []


def test_inject_returns_unchanged_when_abimmodule_unavailable() -> None:
    """When ABIModule is not initialised (e.g. unit tests), retrieval should be a no-op."""
    service = _make_service_with_no_adapter()
    msgs = [_msg("user", "Tell me about the document.")]
    # ABIModule.get_instance() will raise or return None in this context → graceful fallback
    result, sources = service._inject_chat_vector_context(
        provider_messages=msgs,
        conversation_id="conv-1",
        user_id="u",
        embedding_model="hash-v1",
        embedding_dimension=32,
    )
    # Should return the original messages unchanged (no crash)
    assert result is msgs or result == msgs
    assert sources == []


def test_inject_returns_unchanged_when_collection_does_not_exist(monkeypatch) -> None:
    """If the collection is absent the chat flow must continue without retrieval."""

    @dataclass
    class _FakeVectorStore:
        def list_collections(self):
            return []  # collection does not exist

    class _FakeEngine:
        class services:
            vector_store = _FakeVectorStore()

    class _FakeModule:
        engine = _FakeEngine()

        @classmethod
        def get_instance(cls):
            return cls()

    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.chat.service.ABIModule",
        _FakeModule,
        raising=False,
    )

    service = _make_service_with_no_adapter()
    msgs = [_msg("user", "Tell me about the document.")]
    result, sources = service._inject_chat_vector_context(
        provider_messages=msgs,
        conversation_id="conv-1",
        user_id="u",
        embedding_model="hash-v1",
        embedding_dimension=32,
    )
    assert result == msgs
    assert sources == []


def test_inject_augments_user_message_when_collection_exists(monkeypatch) -> None:
    """When matching chunks exist the last user message must include the context block."""
    from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings import (
        build_chat_collection_name,
    )

    @dataclass
    class _FakeMatch:
        metadata: dict
        payload: dict
        score: float = 0.9

    class _FakeVectorStore:
        def list_collections(self):
            return [build_chat_collection_name("conv-1")]

        def search_similar(self, collection_name, query_vector, k, **kwargs):
            return [
                _FakeMatch(
                    metadata={"user_id": "u", "filename": "report.txt"},
                    payload={"text": "Important fact from the document."},
                )
            ]

    class _FakeEngine:
        class services:
            vector_store = _FakeVectorStore()

    class _FakeModule:
        engine = _FakeEngine()

        @classmethod
        def get_instance(cls):
            return cls()

    monkeypatch.setattr("naas_abi.ABIModule", _FakeModule, raising=False)

    service = _make_service_with_no_adapter()
    msgs = [_msg("user", "Tell me about the document.")]
    result, sources = service._inject_chat_vector_context(
        provider_messages=msgs,
        conversation_id="conv-1",
        user_id="u",
        embedding_model="hash-v1",
        embedding_dimension=32,
    )

    assert len(result) == 1
    assert "DOCUMENT CONTEXT" in result[0].content
    assert "Important fact from the document." in result[0].content
    assert sources == ["report.txt"]


def test_inject_skips_chunks_from_other_users(monkeypatch) -> None:
    """Chunks belonging to a different user must not be injected (user isolation)."""
    from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings import (
        build_chat_collection_name,
    )

    @dataclass
    class _FakeMatch:
        metadata: dict
        payload: dict
        score: float = 0.9

    class _FakeVectorStore:
        def list_collections(self):
            return [build_chat_collection_name("conv-1")]

        def search_similar(self, collection_name, query_vector, k, **kwargs):
            return [
                _FakeMatch(
                    metadata={"user_id": "other-user", "filename": "secret.txt"},
                    payload={"text": "Secret data belonging to another user."},
                )
            ]

    class _FakeEngine:
        class services:
            vector_store = _FakeVectorStore()

    class _FakeModule:
        engine = _FakeEngine()

        @classmethod
        def get_instance(cls):
            return cls()

    monkeypatch.setattr("naas_abi.ABIModule", _FakeModule, raising=False)

    service = _make_service_with_no_adapter()
    msgs = [_msg("user", "Tell me about the document.")]
    result, sources = service._inject_chat_vector_context(
        provider_messages=msgs,
        conversation_id="conv-1",
        user_id="u",    # different from "other-user"
        embedding_model="hash-v1",
        embedding_dimension=32,
    )
    # No chunks from other-user → message must be unaugmented
    assert result == msgs
    assert sources == []


# ---------------------------------------------------------------------------
# Tests: build_system_prompt (user profile injection on first turn)
# ---------------------------------------------------------------------------

def _user_record(
    name: str = "Alice Smith",
    email: str = "alice@example.com",
    company: str | None = None,
    role: str | None = None,
    bio: str | None = None,
) -> AuthUserRecord:
    return AuthUserRecord(
        id="user-1",
        email=email,
        name=name,
        hashed_password="x",
        created_at=datetime.now(),
        company=company,
        role=role,
        bio=bio,
    )


@pytest.mark.asyncio
async def test_build_system_prompt_injects_user_on_first_turn() -> None:
    auth_adapter = SimpleNamespace(
        get_user_by_id=AsyncMock(
            return_value=_user_record(
                company="Acme Corp",
                role="CTO",
                bio="Loves bicycles.",
            )
        )
    )
    service = ChatService(adapter=SimpleNamespace(), auth_adapter=auth_adapter)

    prompt = await service.build_system_prompt(
        agent="aia",
        explicit_system_prompt=None,
        prior_messages=[ChatInputMessage(role="user", content="hi")],
        user_id="user-1",
    )

    assert AGENT_SYSTEM_PROMPTS["aia"] in prompt
    assert "Name: Alice Smith" in prompt
    assert "Email: alice@example.com" in prompt
    assert "Company: Acme Corp" in prompt
    assert "Role: CTO" in prompt
    assert "Bio: Loves bicycles." in prompt
    auth_adapter.get_user_by_id.assert_awaited_once_with("user-1")


@pytest.mark.asyncio
async def test_build_system_prompt_omits_empty_user_fields() -> None:
    auth_adapter = SimpleNamespace(
        get_user_by_id=AsyncMock(return_value=_user_record())
    )
    service = ChatService(adapter=SimpleNamespace(), auth_adapter=auth_adapter)

    prompt = await service.build_system_prompt(
        agent="aia",
        explicit_system_prompt=None,
        prior_messages=[],
        user_id="user-1",
    )

    assert "Name: Alice Smith" in prompt
    assert "Email: alice@example.com" in prompt
    assert "Company:" not in prompt
    assert "Role:" not in prompt
    assert "Bio:" not in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_skips_user_when_prior_assistant_message() -> None:
    auth_adapter = SimpleNamespace(get_user_by_id=AsyncMock())
    service = ChatService(adapter=SimpleNamespace(), auth_adapter=auth_adapter)

    prompt = await service.build_system_prompt(
        agent="aia",
        explicit_system_prompt=None,
        prior_messages=[
            ChatInputMessage(role="user", content="hi"),
            ChatInputMessage(role="assistant", content="hello"),
        ],
        user_id="user-1",
    )

    assert "Name:" not in prompt
    assert "MULTI-AGENT NOTICE" in prompt
    auth_adapter.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_build_system_prompt_without_auth_adapter_returns_base() -> None:
    service = ChatService(adapter=SimpleNamespace())

    prompt = await service.build_system_prompt(
        agent="aia",
        explicit_system_prompt=None,
        prior_messages=[],
        user_id="user-1",
    )

    assert prompt == AGENT_SYSTEM_PROMPTS["aia"]


@pytest.mark.asyncio
async def test_build_system_prompt_swallows_auth_errors() -> None:
    auth_adapter = SimpleNamespace(
        get_user_by_id=AsyncMock(side_effect=RuntimeError("db down"))
    )
    service = ChatService(adapter=SimpleNamespace(), auth_adapter=auth_adapter)

    prompt = await service.build_system_prompt(
        agent="aia",
        explicit_system_prompt=None,
        prior_messages=[],
        user_id="user-1",
    )

    assert prompt == AGENT_SYSTEM_PROMPTS["aia"]


@pytest.mark.asyncio
async def test_build_system_prompt_respects_explicit_override() -> None:
    auth_adapter = SimpleNamespace(
        get_user_by_id=AsyncMock(return_value=_user_record())
    )
    service = ChatService(adapter=SimpleNamespace(), auth_adapter=auth_adapter)

    prompt = await service.build_system_prompt(
        agent="aia",
        explicit_system_prompt="CUSTOM PROMPT",
        prior_messages=[],
        user_id="user-1",
    )

    assert prompt.startswith("CUSTOM PROMPT")
    assert "Name: Alice Smith" in prompt


@pytest.mark.asyncio
async def test_build_user_context_addendum_returns_block_on_first_turn() -> None:
    auth_adapter = SimpleNamespace(
        get_user_by_id=AsyncMock(
            return_value=_user_record(name="Bob", email="bob@example.com", role="PM")
        )
    )
    service = ChatService(adapter=SimpleNamespace(), auth_adapter=auth_adapter)

    addendum = await service.build_user_context_addendum(
        prior_messages=[],
        user_id="user-1",
    )

    assert "Name: Bob" in addendum
    assert "Email: bob@example.com" in addendum
    assert "Role: PM" in addendum


@pytest.mark.asyncio
async def test_build_user_context_addendum_empty_when_prior_assistant() -> None:
    auth_adapter = SimpleNamespace(
        get_user_by_id=AsyncMock(return_value=_user_record())
    )
    service = ChatService(adapter=SimpleNamespace(), auth_adapter=auth_adapter)

    addendum = await service.build_user_context_addendum(
        prior_messages=[SimpleNamespace(role="assistant", content="hi")],
        user_id="user-1",
    )

    assert addendum == ""
    auth_adapter.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_build_user_context_addendum_empty_without_auth_adapter() -> None:
    service = ChatService(adapter=SimpleNamespace(), auth_adapter=None)

    addendum = await service.build_user_context_addendum(
        prior_messages=[],
        user_id="user-1",
    )

    assert addendum == ""


@pytest.mark.asyncio
async def test_build_user_context_addendum_empty_when_lookup_fails() -> None:
    auth_adapter = SimpleNamespace(
        get_user_by_id=AsyncMock(side_effect=RuntimeError("db down"))
    )
    service = ChatService(adapter=SimpleNamespace(), auth_adapter=auth_adapter)

    addendum = await service.build_user_context_addendum(
        prior_messages=[],
        user_id="user-1",
    )

    assert addendum == ""
