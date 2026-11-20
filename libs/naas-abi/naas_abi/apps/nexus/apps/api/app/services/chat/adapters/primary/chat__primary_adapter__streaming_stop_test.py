"""Stop ends a turn: its agent call is cancelled, its reply saved as stopped with
what it had written. Leaving the stream (a reload, a navigation) stops nothing."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

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

FIRST_PART = "Searching your drafts. "
LAST_PART = "Deleted 3 drafts."


class _DelegatedTurn:
    """Writes a first part, calls a tool, then waits on the sub-agent's answer."""

    def __init__(self) -> None:
        self.waiting = asyncio.Event()
        self.answer_ready = asyncio.Event()
        self.cancelled = False
        self.saw_stop: bool | None = None
        self.contents: list[str] = []
        self.metadata: list[dict[str, Any]] = []


def _install(monkeypatch) -> _DelegatedTurn:
    _install_fakes(monkeypatch, [])
    turn = _DelegatedTurn()

    async def save_content(*, full_response: str, **_kwargs) -> None:
        turn.contents.append(full_response)

    async def save_metadata(*, metadata: dict[str, Any], **_kwargs) -> None:
        turn.metadata.append(metadata)

    async def agent_call(messages, config, **_kwargs):
        from naas_abi_core.services.agent.context import turn_stopped

        try:
            yield FIRST_PART
            yield {"event": "tool_usage", "tool": "delete_files"}
            turn.waiting.set()
            await turn.answer_ready.wait()
            yield LAST_PART
        except asyncio.CancelledError:
            turn.cancelled = True
            raise
        finally:
            turn.saw_stop = turn_stopped()

    monkeypatch.setattr(streaming, "persist_stream_content", save_content)
    monkeypatch.setattr(streaming, "persist_stream_metadata", save_metadata)
    monkeypatch.setattr(remote_streaming, "stream_with_remote_agent", agent_call)
    return turn


async def _start_turn():
    response = await streaming.stream_chat_response(
        request=ChatRequest(conversation_id="conv-1", message="delete my drafts", agent="a-9"),
        current_user=SimpleNamespace(id="user-1"),
    )
    frames = response.body_iterator
    assert "assistant_message_id" in await anext(frames)
    return frames


async def _until_saved(turn: _DelegatedTurn) -> None:
    for _ in range(200):
        if turn.metadata:
            return
        await asyncio.sleep(0.01)


def test_stop_cancels_the_agent_call_and_saves_the_reply_as_stopped(monkeypatch) -> None:
    async def scenario() -> tuple[_DelegatedTurn, int, list[str]]:
        turn = _install(monkeypatch)
        frames = await _start_turn()
        await turn.waiting.wait()
        stopped = await streaming.stop_turns("conv-1")
        return turn, stopped, [frame async for frame in frames]

    turn, stopped, rest = asyncio.run(scenario())

    assert stopped == 1
    # The call in flight is cancelled (a remote agent's run with it) and saw the
    # stop flag that keeps an in-process agent from its next model or tool call.
    assert turn.cancelled is True
    assert turn.saw_stop is True
    assert turn.contents[-1] == FIRST_PART
    assert turn.metadata[-1]["turn_status"] == "stopped"
    assert not any(LAST_PART in frame for frame in rest)
    assert streaming._TURNS_IN_FLIGHT == {}


def test_leaving_the_stream_stops_nothing(monkeypatch) -> None:
    async def scenario() -> _DelegatedTurn:
        turn = _install(monkeypatch)
        frames = await _start_turn()
        await turn.waiting.wait()
        await frames.aclose()  # a reload
        turn.answer_ready.set()
        await _until_saved(turn)
        return turn

    turn = asyncio.run(scenario())

    assert turn.cancelled is False
    assert turn.saw_stop is False
    assert turn.contents[-1] == FIRST_PART + LAST_PART
    assert turn.metadata[-1]["turn_status"] == "done"


def test_stop_reaches_only_the_turns_of_its_conversation(monkeypatch) -> None:
    async def scenario() -> tuple[_DelegatedTurn, int]:
        turn = _install(monkeypatch)
        frames = await _start_turn()
        await turn.waiting.wait()
        stopped = await streaming.stop_turns("conv-2")
        turn.answer_ready.set()
        [frame async for frame in frames]
        return turn, stopped

    turn, stopped = asyncio.run(scenario())

    assert stopped == 0
    assert turn.cancelled is False
    assert turn.metadata[-1]["turn_status"] == "done"
