"""pi adapter tests against a fake ``pi --mode rpc`` subprocess.

The fake speaks the documented JSONL protocol: commands arrive on stdin,
scripted responses/events are replayed on stdout. No binary, no network.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import pytest

from desktop.harness.adapters.pi import PiHarnessAdapter
from desktop.harness.models import (
    DoneEvent,
    ErrorEvent,
    ReasoningEvent,
    TextEvent,
    ToolEvent,
)
from desktop.harness.port import HarnessUnavailableError

_FAKE_WORKSPACE = "/tmp/ws"  # nosec B108


class _FakeStdin:
    def __init__(self, on_command: Callable[[dict[str, Any]], None]):
        self._on_command = on_command
        self.lines: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.lines.append(data)
        for line in data.split(b"\n"):
            if line.strip():
                self._on_command(json.loads(line))

    async def drain(self) -> None:
        pass


class _FakeStdout:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    def push(self, payload: dict[str, Any]) -> None:
        self._queue.put_nowait(json.dumps(payload).encode("utf-8") + b"\n")

    def push_eof(self) -> None:
        self._queue.put_nowait(b"")

    async def readline(self) -> bytes:
        return await self._queue.get()


class FakePiProcess:
    """Scripted pi RPC process: ``script`` maps command type to the JSONL
    payloads to emit when that command arrives."""

    def __init__(self, script: dict[str, list[dict[str, Any]]] | None = None):
        self.script = script or {}
        self.stdout = _FakeStdout()
        self.stdin = _FakeStdin(self._handle_command)
        self.returncode: int | None = None
        self.received: list[dict[str, Any]] = []
        self.spawn_args: list[str] = []
        self.spawn_cwd = ""

    def _handle_command(self, command: dict[str, Any]) -> None:
        self.received.append(command)
        for payload in self.script.get(command["type"], []):
            out = dict(payload)
            # Correlate responses with the incoming command id, like pi does.
            if out.get("type") == "response" and "id" not in out:
                if "id" in command:
                    out["id"] = command["id"]
            self.stdout.push(out)

    def terminate(self) -> None:
        self.returncode = 0
        self.stdout.push_eof()

    async def wait(self) -> int:
        return 0


def _factory(*processes: FakePiProcess):
    remaining = list(processes)

    async def spawn(args: list[str], cwd: str) -> FakePiProcess:
        proc = remaining.pop(0)
        proc.spawn_args = args
        proc.spawn_cwd = cwd
        return proc

    return spawn


def _adapter(*processes: FakePiProcess, which=lambda name: "/usr/local/bin/pi"):
    return PiHarnessAdapter(
        workspace_root=_FAKE_WORKSPACE,
        process_factory=_factory(*processes),
        which=which,
    )


PROMPT_SCRIPT: dict[str, list[dict[str, Any]]] = {
    "prompt": [
        {"type": "response", "command": "prompt", "success": True},
        {"type": "agent_start"},
        {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "thinking_delta",
                "contentIndex": 0,
                "delta": "hmm",
            },
        },
        {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "text_delta",
                "contentIndex": 1,
                "delta": "Hello ",
            },
        },
        {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "text_delta",
                "contentIndex": 1,
                "delta": "world",
            },
        },
        {
            "type": "tool_execution_start",
            "toolCallId": "call_1",
            "toolName": "bash",
            "args": {"command": "ls -la"},
        },
        {
            "type": "tool_execution_update",
            "toolCallId": "call_1",
            "toolName": "bash",
            "args": {"command": "ls -la"},
            "partialResult": {"content": [{"type": "text", "text": "partial"}]},
        },
        {
            "type": "tool_execution_end",
            "toolCallId": "call_1",
            "toolName": "bash",
            "result": {"content": [{"type": "text", "text": "total 48"}]},
            "isError": False,
        },
        {
            "type": "agent_end",
            "messages": [
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hello world"}],
                },
            ],
        },
    ]
}


@pytest.mark.asyncio
async def test_stream_prompt_normalizes_pi_events() -> None:
    proc = FakePiProcess(script=PROMPT_SCRIPT)
    adapter = _adapter(proc)
    session_id = await adapter.create_session("My chat")

    events = [e async for e in adapter.stream_prompt(session_id, "hi")]

    assert isinstance(events[0], ReasoningEvent)
    # Text is cumulative per part, matching the legacy opencode contract.
    text_events = [e for e in events if isinstance(e, TextEvent)]
    assert [e.text for e in text_events] == ["Hello ", "Hello world"]
    assert text_events[0].part_id == text_events[1].part_id

    tool_events = [e for e in events if isinstance(e, ToolEvent)]
    assert [e.status for e in tool_events] == ["running", "running", "completed"]
    assert tool_events[0].call_id == "call_1"
    assert tool_events[0].title == "ls -la"
    assert tool_events[0].input == {"command": "ls -la"}
    assert tool_events[2].output == "total 48"

    assert events[-1] == DoneEvent(text="Hello world")
    assert not any(isinstance(e, ErrorEvent) for e in events)


@pytest.mark.asyncio
async def test_stream_prompt_sets_model_before_prompting() -> None:
    script = dict(PROMPT_SCRIPT)
    script["set_model"] = [
        {"type": "response", "command": "set_model", "success": True, "data": {}}
    ]
    proc = FakePiProcess(script=script)
    adapter = _adapter(proc)
    session_id = await adapter.create_session("chat")

    events = [
        e
        async for e in adapter.stream_prompt(
            session_id, "hi", model="anthropic/claude-4"
        )
    ]

    assert proc.received[0] == {
        "type": "set_model",
        "provider": "anthropic",
        "modelId": "claude-4",
        "id": "set-model",
    }
    assert proc.received[1]["type"] == "prompt"
    assert proc.received[1]["message"] == "hi"
    assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_stream_prompt_surfaces_rejected_prompt() -> None:
    proc = FakePiProcess(
        script={
            "prompt": [
                {
                    "type": "response",
                    "command": "prompt",
                    "success": False,
                    "error": "agent is streaming",
                }
            ]
        }
    )
    adapter = _adapter(proc)
    session_id = await adapter.create_session("chat")

    events = [e async for e in adapter.stream_prompt(session_id, "hi")]

    assert events[0] == ErrorEvent(message="agent is streaming")
    assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_stream_prompt_handles_process_death() -> None:
    proc = FakePiProcess(script={"prompt": []})
    adapter = _adapter(proc)
    session_id = await adapter.create_session("chat")
    # Simulate crash: stdout closes with no agent_end.
    proc.stdout.push_eof()

    events = [e async for e in adapter.stream_prompt(session_id, "hi")]

    assert any(isinstance(e, ErrorEvent) for e in events)
    assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_create_session_spawns_rpc_process_in_workspace() -> None:
    proc = FakePiProcess()
    adapter = _adapter(proc)
    session_id = await adapter.create_session("My chat")

    assert session_id.startswith("pi_")
    assert proc.spawn_args[:3] == ["pi", "--mode", "rpc"]
    assert "--name" in proc.spawn_args
    assert proc.spawn_cwd == _FAKE_WORKSPACE


@pytest.mark.asyncio
async def test_delete_session_terminates_process() -> None:
    proc = FakePiProcess()
    adapter = _adapter(proc)
    session_id = await adapter.create_session("chat")
    await adapter.delete_session(session_id)
    assert proc.returncode == 0


@pytest.mark.asyncio
async def test_abort_sends_abort_command() -> None:
    proc = FakePiProcess()
    adapter = _adapter(proc)
    session_id = await adapter.create_session("chat")
    await adapter.abort(session_id)
    assert {"type": "abort"} in proc.received


@pytest.mark.asyncio
async def test_health_and_start_reflect_binary_presence() -> None:
    available = _adapter(FakePiProcess())
    assert await available.health() is True
    await available.start()  # must not raise

    missing = PiHarnessAdapter(workspace_root=_FAKE_WORKSPACE, which=lambda name: None)
    assert await missing.health() is False
    with pytest.raises(HarnessUnavailableError, match="pi binary not found"):
        await missing.start()


@pytest.mark.asyncio
async def test_list_models_groups_by_provider_and_disposes_process() -> None:
    proc = FakePiProcess(
        script={
            "get_available_models": [
                {
                    "type": "response",
                    "command": "get_available_models",
                    "success": True,
                    "data": {
                        "models": [
                            {
                                "id": "claude-4",
                                "name": "Claude 4",
                                "provider": "anthropic",
                            },
                            {"id": "gpt-6", "name": "GPT-6", "provider": "openai"},
                            {
                                "id": "claude-3",
                                "name": "Claude 3",
                                "provider": "anthropic",
                            },
                        ]
                    },
                }
            ]
        }
    )
    adapter = _adapter(proc)
    providers = await adapter.list_models()

    assert [p.id for p in providers] == ["anthropic", "openai"]
    assert [m.id for m in providers[0].models] == ["claude-4", "claude-3"]
    assert proc.returncode == 0  # transient process torn down


@pytest.mark.asyncio
async def test_stop_terminates_all_sessions() -> None:
    first, second = FakePiProcess(), FakePiProcess()
    adapter = _adapter(first, second)
    await adapter.create_session("a")
    await adapter.create_session("b")
    await adapter.stop()
    assert first.returncode == 0
    assert second.returncode == 0


@pytest.mark.asyncio
async def test_stale_session_id_reattaches_fresh_process() -> None:
    dead, fresh = FakePiProcess(), FakePiProcess(script=PROMPT_SCRIPT)
    adapter = _adapter(dead, fresh)
    session_id = await adapter.create_session("chat")
    dead.returncode = 1  # process died behind our back

    events = [e async for e in adapter.stream_prompt(session_id, "hi")]

    assert fresh.received[0]["type"] == "prompt"
    assert isinstance(events[-1], DoneEvent)
