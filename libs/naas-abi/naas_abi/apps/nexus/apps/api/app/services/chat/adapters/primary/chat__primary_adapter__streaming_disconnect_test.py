"""A client that leaves mid-turn: the turn still persists its answer."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.services.agents.remote import streaming as remote_streaming
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary import (
    chat__primary_adapter__streaming as streaming,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__streaming_remote_test import (
    _install_fakes,
)

ANSWER = "Here are the files in your workspace."


async def _leave_mid_turn(monkeypatch) -> list[str]:
    _install_fakes(monkeypatch, [])
    persisted: list[str] = []
    answer_ready = asyncio.Event()

    async def record(*, full_response: str, **_kwargs) -> None:
        persisted.append(full_response)

    async def delegated_turn(messages, config, **_kwargs):
        # A supervisor's handoff: steps first, the sub-agent's whole answer last.
        yield {"event": "tool_usage", "tool": "transfer_to_Files"}
        await answer_ready.wait()
        yield ANSWER

    monkeypatch.setattr(streaming, "persist_stream_content", record)
    monkeypatch.setattr(remote_streaming, "stream_with_remote_agent", delegated_turn)

    response = await streaming.stream_chat_response(
        request=ChatRequest(conversation_id="conv-1", message="list my files", agent="a-9"),
        current_user=SimpleNamespace(id="user-1"),
    )
    frames = response.body_iterator
    assert "assistant_message_id" in await anext(frames)
    assert "transfer_to_Files" in await anext(frames)
    await frames.aclose()  # the client reloads before the answer

    answer_ready.set()
    for _ in range(200):
        if persisted and persisted[-1] == ANSWER:
            break
        await asyncio.sleep(0.01)
    return persisted


def test_a_turn_whose_client_leaves_still_persists_its_answer(monkeypatch) -> None:
    persisted = asyncio.run(_leave_mid_turn(monkeypatch))

    assert persisted and persisted[-1] == ANSWER
