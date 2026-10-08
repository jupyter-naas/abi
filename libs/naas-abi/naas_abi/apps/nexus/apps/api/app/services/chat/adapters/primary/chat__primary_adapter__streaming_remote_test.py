"""A chat turn with an agent published by a remote module, driven end to end."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.agents.remote import streaming as remote_streaming
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary import (
    chat__primary_adapter__streaming as streaming,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest,
)


def _install_fakes(monkeypatch, calls: list[dict[str, Any]]) -> None:
    provider = SimpleNamespace(
        id="remote-a-9",
        name="Remote (acme.research)",
        type="remote",
        enabled=True,
        endpoint=None,
        api_key=None,
        account_id=None,
        model="acme.research/Researcher",
        llm_model=None,
    )

    async def fake_resolve_provider(*_args, **_kwargs):
        return provider

    @asynccontextmanager
    async def fake_session():
        async def _noop() -> None:
            return None

        yield SimpleNamespace(commit=_noop, rollback=_noop)

    class _FakeChat:
        def _inject_chat_vector_context(self, provider_messages, **_kwargs):
            return provider_messages, []

        async def build_system_prompt(self, **_kwargs) -> str:
            return "system"

        async def build_abi_injection_preamble(self, **_kwargs) -> str:
            return "SKILLS CATALOG"

        async def build_remote_agent_preamble(self, **_kwargs) -> str:
            return "USER PROFILE"

        async def create_streaming_message_pair(self, **_kwargs):
            return None, "assistant-msg-1"

    @contextmanager
    def fake_bind_registry(_db):
        yield SimpleNamespace(chat=_FakeChat())

    async def fake_conversation(**_kwargs) -> str:
        return "conv-1"

    async def fake_messages(**_kwargs) -> list[Any]:
        return []

    async def noop(**_kwargs) -> None:
        return None

    async def fake_remote(messages, config, *, thread_id, user_context_preamble, invocation_id):
        calls.append(
            {
                "model": config.model,
                "thread_id": thread_id,
                "invocation_id": invocation_id,
                "preamble": user_context_preamble,
            }
        )
        yield {"event": "tool_usage", "tool": "search"}
        yield "JetStream persists streams."

    monkeypatch.setattr(streaming, "resolve_provider", fake_resolve_provider)
    monkeypatch.setattr(streaming, "AsyncSessionLocal", fake_session)
    monkeypatch.setattr(streaming, "bind_registry", fake_bind_registry)
    monkeypatch.setattr(streaming, "get_or_create_conversation", fake_conversation)
    monkeypatch.setattr(streaming, "build_provider_messages_with_agents", fake_messages)
    monkeypatch.setattr(streaming, "request_context", lambda user: SimpleNamespace(user=user))
    monkeypatch.setattr(streaming, "persist_stream_content", noop)
    monkeypatch.setattr(streaming, "persist_stream_metadata", noop)
    monkeypatch.setattr(remote_streaming, "stream_with_remote_agent", fake_remote)


async def _frames(monkeypatch, calls) -> list[dict[str, Any]]:
    _install_fakes(monkeypatch, calls)
    response = await streaming.stream_chat_response(
        request=ChatRequest(conversation_id="conv-1", message="what is JetStream?", agent="a-9"),
        current_user=SimpleNamespace(id="user-1"),
    )
    frames = []
    async for chunk in response.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
        for line in text.splitlines():
            payload = line.removeprefix("data: ").strip()
            if line.startswith("data: ") and payload != "[DONE]":
                frames.append(json.loads(payload))
    return frames


def test_remote_turn_streams_through_the_remote_agent(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    frames = asyncio.run(_frames(monkeypatch, calls))

    assert calls == [
        {
            "model": "acme.research/Researcher",
            "thread_id": "conv-1",
            "invocation_id": "assistant-msg-1",
            "preamble": "USER PROFILE",
        }
    ]
    assert {"content": "JetStream persists streams."} in frames
    assert any(f.get("event") == "tool_usage" for f in frames)
    assert not any("error" in f for f in frames)
