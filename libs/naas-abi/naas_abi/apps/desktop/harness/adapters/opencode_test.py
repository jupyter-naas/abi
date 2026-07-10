"""Opencode adapter tests.

Two layers, both offline:

- Translation tests against a fake ``OpencodeClient`` (duck-typed) that
  replays the legacy dict events.
- An end-to-end test driving the real ``OpencodeClient`` through an
  ``httpx.MockTransport`` fake of the opencode HTTP/SSE API.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
import pytest

from desktop.harness.adapters.opencode import OpencodeHarnessAdapter
from desktop.harness.models import (
    DoneEvent,
    ErrorEvent,
    ReasoningEvent,
    TextEvent,
    ToolEvent,
)
from desktop.harness.port import HarnessUnavailableError
from desktop.core.opencode_client import OpencodeClient, OpencodeUnavailableError

_FAKE_WORKSPACE = "/tmp/ws"  # nosec B108


class FakeOpencodeClient:
    """Duck-typed stand-in replaying scripted legacy events."""

    def __init__(self, events: list[dict[str, Any]] | None = None):
        self.events = events or []
        self.workdir = _FAKE_WORKSPACE
        self.opencode_bin = "opencode"
        self.port: int | None = 4242
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.running = True
        self.providers_payload: list[dict[str, Any]] = []

    def start(self) -> None:
        self.calls.append(("start", ()))

    def stop(self) -> None:
        self.calls.append(("stop", ()))
        self.running = False

    def restart(self, workdir=None, opencode_bin=None) -> None:
        self.calls.append(("restart", (workdir, opencode_bin)))

    def is_running(self) -> bool:
        return self.running

    async def providers(self) -> list[dict[str, Any]]:
        return self.providers_payload

    async def create_session(self, title: str) -> str:
        self.calls.append(("create_session", (title,)))
        return "ses_123"

    async def abort(self, session_id: str) -> None:
        self.calls.append(("abort", (session_id,)))

    async def stream_message(
        self, session_id, text, model=None, agent=None
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append(("stream_message", (session_id, text, model, agent)))
        for event in self.events:
            yield event


def _adapter(fake: FakeOpencodeClient) -> OpencodeHarnessAdapter:
    return OpencodeHarnessAdapter(workspace_root=_FAKE_WORKSPACE, client=fake)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_stream_prompt_translates_legacy_events() -> None:
    fake = FakeOpencodeClient(
        events=[
            {"type": "reasoning"},
            {"type": "text", "text": "Hel", "part_id": "p1"},
            {"type": "text", "text": "Hello", "part_id": "p1"},
            {
                "type": "tool",
                "tool": "bash",
                "status": "running",
                "title": "ls",
                "call_id": "c1",
            },
            {
                "type": "tool",
                "tool": "bash",
                "status": "completed",
                "title": "ls",
                "call_id": "c1",
            },
            {"type": "error", "message": "quota"},
            {"type": "complete", "text": "Hello"},
        ]
    )
    events = [
        e async for e in _adapter(fake).stream_prompt("ses_123", "hi", model="a/m")
    ]

    assert isinstance(events[0], ReasoningEvent)
    assert events[1] == TextEvent(text="Hel", part_id="p1")
    assert events[2] == TextEvent(text="Hello", part_id="p1")
    assert events[3] == ToolEvent(
        call_id="c1", name="bash", status="running", title="ls"
    )
    assert events[4].to_dict()["status"] == "completed"
    assert events[5] == ErrorEvent(message="quota")
    assert events[6] == DoneEvent(text="Hello")
    # model/agent pass through untouched
    assert fake.calls[-1] == ("stream_message", ("ses_123", "hi", "a/m", None))


@pytest.mark.asyncio
async def test_stream_prompt_appends_done_when_legacy_stream_ends_early() -> None:
    fake = FakeOpencodeClient(
        events=[{"type": "text", "text": "partial", "part_id": "p"}]
    )
    events = [e async for e in _adapter(fake).stream_prompt("s", "hi")]
    assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_lifecycle_and_sessions_delegate_to_client() -> None:
    fake = FakeOpencodeClient()
    adapter = _adapter(fake)

    await adapter.start()
    assert await adapter.health() is True
    session_id = await adapter.create_session("My chat")
    assert session_id == "ses_123"
    await adapter.abort(session_id)
    await adapter.restart(workspace_root="/fake/other", binary="oc2")
    await adapter.stop()

    names = [name for name, _ in fake.calls]
    assert names == ["start", "create_session", "abort", "restart", "stop"]
    assert ("restart", ("/fake/other", "oc2")) in fake.calls


@pytest.mark.asyncio
async def test_start_wraps_unavailable_error() -> None:
    fake = FakeOpencodeClient()

    def failing_start() -> None:
        raise OpencodeUnavailableError("no binary")

    fake.start = failing_start  # type: ignore[method-assign]
    with pytest.raises(HarnessUnavailableError, match="no binary"):
        await _adapter(fake).start()


@pytest.mark.asyncio
async def test_list_models_maps_providers() -> None:
    fake = FakeOpencodeClient()
    fake.providers_payload = [
        {
            "id": "anthropic",
            "name": "Anthropic",
            "models": [{"id": "claude-4", "name": "Claude 4"}, {"id": None}],
        }
    ]
    providers = await _adapter(fake).list_models()
    assert len(providers) == 1
    assert providers[0].id == "anthropic"
    assert [m.to_dict() for m in providers[0].models] == [
        {"id": "claude-4", "name": "Claude 4", "supports_tools": True}
    ]


# -- end-to-end through the real OpencodeClient over MockTransport ----------


def _sse(events: list[dict[str, Any]]) -> bytes:
    return b"".join(
        f"data: {json.dumps(event)}\n\n".encode("utf-8") for event in events
    )


def _fake_opencode_handler(session_id: str) -> Any:
    """Fake opencode HTTP API: session create, prompt POST, SSE stream."""

    stream_events = [
        {
            "type": "message.updated",
            "properties": {
                "sessionID": session_id,
                "info": {"role": "assistant", "id": "msg_1"},
            },
        },
        {
            "type": "message.part.updated",
            "properties": {
                "sessionID": session_id,
                "part": {
                    "type": "text",
                    "id": "prt_1",
                    "messageID": "msg_1",
                    "text": "Hi there",
                },
            },
        },
        {
            "type": "message.part.updated",
            "properties": {
                "sessionID": session_id,
                "part": {
                    "type": "tool",
                    "id": "prt_2",
                    "messageID": "msg_1",
                    "tool": "bash",
                    "callID": "call_1",
                    "state": {"status": "completed", "title": "ls -la"},
                },
            },
        },
        {"type": "session.idle", "properties": {"sessionID": session_id}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/session" and request.method == "POST":
            return httpx.Response(200, json={"id": session_id})
        if path == f"/session/{session_id}" and request.method == "DELETE":
            return httpx.Response(200, json={"status": "deleted"})
        if path == f"/session/{session_id}/message" and request.method == "POST":
            return httpx.Response(
                200,
                json={"parts": [{"type": "text", "text": "Hi there"}]},
            )
        if path == "/event":
            return httpx.Response(
                200,
                content=_sse(stream_events),
                headers={"content-type": "text/event-stream"},
            )
        if path == "/config/providers":
            return httpx.Response(
                200,
                json={
                    "providers": [
                        {
                            "id": "anthropic",
                            "name": "Anthropic",
                            "models": {"claude-4": {"name": "Claude 4"}},
                        }
                    ]
                },
            )
        return httpx.Response(404)

    return handler


@pytest.mark.asyncio
async def test_end_to_end_with_httpx_mock_transport() -> None:
    session_id = "ses_mock"
    transport = httpx.MockTransport(_fake_opencode_handler(session_id))

    client = OpencodeClient(
        workdir=_FAKE_WORKSPACE,
        base_url="http://opencode.test",
        transport=transport,
    )
    adapter = OpencodeHarnessAdapter(workspace_root=_FAKE_WORKSPACE, client=client)

    created = await adapter.create_session("chat")
    assert created == session_id

    providers = await adapter.list_models()
    assert providers[0].models[0] == providers[0].models[0].__class__(
        id="claude-4", name="Claude 4"
    )

    events = [e async for e in adapter.stream_prompt(session_id, "hello")]
    dicts = [e.to_dict() for e in events]

    assert {"type": "text", "text": "Hi there", "part_id": "prt_1"} in dicts
    tool_events = [d for d in dicts if d["type"] == "tool"]
    assert tool_events and tool_events[0]["call_id"] == "call_1"
    assert tool_events[0]["status"] == "completed"
    assert dicts[-1]["type"] == "complete"
    assert dicts[-1]["text"] == "Hi there"
    assert not any(d["type"] == "error" for d in dicts)

    await adapter.delete_session(session_id)  # 404s would raise via transport
