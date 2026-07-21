"""Tests for OpencodeClient against an in-process fake opencode server.

No real ``opencode`` binary, no network: the fake is an ASGI app wired into
the client through ``httpx.ASGITransport`` (the ``transport`` DI seam on
``OpencodeClient``).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from desktop.core.opencode_client import (
    OpencodeClient,
    _extract_session_error,
    _extract_text,
    _model_payload,
)

_FAKE_WORKDIR = "/tmp"  # nosec B108


class FakeOpencode:
    """Minimal emulation of the ``opencode serve`` HTTP API."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.prompt_response: dict[str, Any] = {}
        self.prompt_status = 200
        self.prompt_delay = 0.0
        self.requests: list[tuple[str, str, Any]] = []

        app = FastAPI()

        @app.post("/session")
        async def create_session(request: Request) -> dict[str, str]:
            self.requests.append(("POST", "/session", await request.json()))
            return {"id": "ses_test"}

        @app.get("/config/providers")
        async def providers() -> dict[str, Any]:
            return {
                "providers": [
                    {
                        "id": "openai",
                        "name": "OpenAI",
                        "models": {"gpt-5": {"name": "GPT-5"}},
                    }
                ]
            }

        @app.post("/session/{session_id}/message")
        async def send_message(session_id: str, request: Request) -> JSONResponse:
            self.requests.append(
                ("POST", f"/session/{session_id}/message", await request.json())
            )
            if self.prompt_delay:
                await asyncio.sleep(self.prompt_delay)
            return JSONResponse(self.prompt_response, status_code=self.prompt_status)

        @app.post("/session/{session_id}/permissions/{permission_id}")
        async def approve(session_id: str, permission_id: str) -> dict[str, str]:
            self.requests.append(
                ("POST", f"/session/{session_id}/permissions/{permission_id}", None)
            )
            return {"status": "ok"}

        @app.post("/session/{session_id}/abort")
        async def abort(session_id: str) -> dict[str, str]:
            self.requests.append(("POST", f"/session/{session_id}/abort", None))
            return {"status": "ok"}

        @app.get("/event")
        async def event_stream() -> StreamingResponse:
            async def stream() -> AsyncIterator[str]:
                for event in self.events:
                    # Let the prompt POST task make progress between events.
                    await asyncio.sleep(0)
                    yield f"data: {json.dumps(event)}\n\n"

            return StreamingResponse(stream(), media_type="text/event-stream")

        self.app = app

    def client(self) -> OpencodeClient:
        return OpencodeClient(
            workdir=_FAKE_WORKDIR,
            base_url="http://fake-opencode",
            transport=httpx.ASGITransport(app=self.app),
        )


SESSION = "ses_test"


def _assistant_message_updated(message_id: str = "msg_a") -> dict[str, Any]:
    return {
        "type": "message.updated",
        "properties": {
            "sessionID": SESSION,
            "info": {"id": message_id, "role": "assistant"},
        },
    }


def _text_part(text: str, message_id: str = "msg_a", part_id: str = "prt_1") -> dict:
    return {
        "type": "message.part.updated",
        "properties": {
            "sessionID": SESSION,
            "part": {
                "type": "text",
                "id": part_id,
                "messageID": message_id,
                "text": text,
            },
        },
    }


def _idle() -> dict[str, Any]:
    return {"type": "session.idle", "properties": {"sessionID": SESSION}}


async def _collect(client: OpencodeClient, **kwargs: Any) -> list[dict[str, Any]]:
    events = []
    async for event in client.stream_message(SESSION, "hello", **kwargs):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_message_part_delta_streams_assistant_text() -> None:
    fake = FakeOpencode()
    fake.events = [
        _assistant_message_updated("msg_a"),
        {
            "type": "message.part.updated",
            "properties": {
                "sessionID": SESSION,
                "part": {
                    "type": "text",
                    "id": "prt_1",
                    "messageID": "msg_a",
                    "text": "",
                },
            },
        },
        {
            "type": "message.part.delta",
            "properties": {
                "sessionID": SESSION,
                "messageID": "msg_a",
                "partID": "prt_1",
                "field": "text",
                "delta": "Hel",
            },
        },
        {
            "type": "message.part.delta",
            "properties": {
                "sessionID": SESSION,
                "messageID": "msg_a",
                "partID": "prt_1",
                "field": "text",
                "delta": "lo",
            },
        },
        _idle(),
    ]
    fake.prompt_response = {"parts": [{"type": "text", "text": "Hello"}]}

    events = await _collect(fake.client())

    texts = [e["text"] for e in events if e["type"] == "text"]
    assert texts == ["", "Hel", "Hello"]
    assert events[-1] == {"type": "complete", "text": "Hello"}


@pytest.mark.asyncio
async def test_message_part_delta_ignores_reasoning_parts() -> None:
    fake = FakeOpencode()
    fake.events = [
        _assistant_message_updated("msg_a"),
        {
            "type": "message.part.updated",
            "properties": {
                "sessionID": SESSION,
                "part": {
                    "type": "reasoning",
                    "id": "prt_r",
                    "messageID": "msg_a",
                    "text": "",
                },
            },
        },
        {
            "type": "message.part.delta",
            "properties": {
                "sessionID": SESSION,
                "messageID": "msg_a",
                "partID": "prt_r",
                "field": "text",
                "delta": "thinking",
            },
        },
        _text_part("done", message_id="msg_a", part_id="prt_t"),
        _idle(),
    ]
    fake.prompt_response = {"parts": [{"type": "text", "text": "done"}]}

    events = await _collect(fake.client())

    texts = [e["text"] for e in events if e["type"] == "text"]
    assert texts == ["done"]
    assert "thinking" not in str(events)


@pytest.mark.asyncio
async def test_assistant_text_streamed_and_user_echo_filtered() -> None:
    fake = FakeOpencode()
    fake.events = [
        _text_part("echo of prompt", message_id="msg_user"),  # user echo
        _assistant_message_updated(),
        _text_part("Hel"),
        _text_part("Hello!"),
        _idle(),
    ]
    fake.prompt_response = {"parts": [{"type": "text", "text": "Hello!"}]}

    events = await _collect(fake.client())

    texts = [e["text"] for e in events if e["type"] == "text"]
    assert texts == ["Hel", "Hello!"]
    assert events[-1] == {"type": "complete", "text": "Hello!"}
    assert not any("echo of prompt" in str(e) for e in events)


@pytest.mark.asyncio
async def test_session_idle_terminates_stream_cleanly() -> None:
    fake = FakeOpencode()
    fake.events = [
        _assistant_message_updated(),
        _text_part("done"),
        _idle(),
        _text_part("never delivered", part_id="prt_2"),
    ]
    fake.prompt_response = {"parts": []}

    events = await _collect(fake.client())

    assert [e["type"] for e in events] == ["text", "complete"]
    assert "never delivered" not in str(events)


@pytest.mark.asyncio
async def test_session_idle_grace_waits_for_slow_prompt_response() -> None:
    fake = FakeOpencode()
    fake.prompt_delay = 0.05  # idle lands before the prompt POST resolves
    fake.events = [
        _assistant_message_updated(),
        _text_part("streamed"),
        _idle(),
    ]
    fake.prompt_response = {"parts": [{"type": "text", "text": "streamed"}]}

    events = await _collect(fake.client())

    assert events[-1] == {"type": "complete", "text": "streamed"}


@pytest.mark.asyncio
async def test_session_error_event_surfaces_error() -> None:
    fake = FakeOpencode()
    fake.events = [
        {
            "type": "session.error",
            "properties": {
                "sessionID": SESSION,
                "error": {
                    "name": "ProviderAuthError",
                    "data": {"message": "invalid API key"},
                },
            },
        },
        _idle(),
    ]
    fake.prompt_response = {"parts": []}

    events = await _collect(fake.client())

    assert {"type": "error", "message": "invalid API key"} in events


@pytest.mark.asyncio
async def test_prompt_response_info_error_surfaces_error() -> None:
    fake = FakeOpencode()
    fake.events = [_idle()]
    fake.prompt_response = {
        "info": {"error": {"name": "UnknownError", "data": {"message": "boom"}}},
        "parts": [],
    }

    events = await _collect(fake.client())

    assert {"type": "error", "message": "boom"} in events


@pytest.mark.asyncio
async def test_prompt_http_error_surfaces_error() -> None:
    fake = FakeOpencode()
    fake.events = [_idle()]
    fake.prompt_response = {"detail": "model not found"}
    fake.prompt_status = 404

    events = await _collect(fake.client())

    errors = [e for e in events if e["type"] == "error"]
    assert len(errors) == 1
    assert "404" in errors[0]["message"]
    assert "model not found" in errors[0]["message"]


@pytest.mark.asyncio
async def test_events_for_other_sessions_ignored() -> None:
    fake = FakeOpencode()
    other = {
        "type": "message.part.updated",
        "properties": {
            "sessionID": "ses_other",
            "part": {
                "type": "text",
                "id": "prt_x",
                "messageID": "msg_a",
                "text": "other session",
            },
        },
    }
    fake.events = [_assistant_message_updated(), other, _idle()]
    fake.prompt_response = {"parts": []}

    events = await _collect(fake.client())

    assert "other session" not in str(events)


@pytest.mark.asyncio
async def test_tool_parts_normalized_and_deduped() -> None:
    def tool_event(status: str) -> dict[str, Any]:
        return {
            "type": "message.part.updated",
            "properties": {
                "sessionID": SESSION,
                "part": {
                    "type": "tool",
                    "id": "prt_t",
                    "callID": "call_1",
                    "tool": "read",
                    "state": {"status": status, "input": {"filePath": "a.py"}},
                },
            },
        }

    fake = FakeOpencode()
    fake.events = [
        _assistant_message_updated(),
        tool_event("running"),
        tool_event("running"),  # duplicate snapshot — must be deduped
        tool_event("completed"),
        _idle(),
    ]
    fake.prompt_response = {"parts": []}

    events = await _collect(fake.client())

    tools = [e for e in events if e["type"] == "tool"]
    assert [(t["tool"], t["status"], t["title"]) for t in tools] == [
        ("read", "running", "a.py"),
        ("read", "completed", "a.py"),
    ]


@pytest.mark.asyncio
async def test_permission_requests_are_approved() -> None:
    fake = FakeOpencode()
    fake.events = [
        {
            "type": "permission.updated",
            "properties": {"sessionID": SESSION, "id": "per_123"},
        },
        _idle(),
    ]
    fake.prompt_response = {"parts": []}

    await _collect(fake.client())

    approvals = [r for r in fake.requests if "/permissions/per_123" in r[1]]
    assert len(approvals) == 1


@pytest.mark.asyncio
async def test_model_and_agent_forwarded_in_prompt_payload() -> None:
    fake = FakeOpencode()
    fake.events = [_idle()]
    fake.prompt_response = {"parts": []}

    await _collect(fake.client(), model="openai/gpt-5", agent="plan")

    prompt = next(r for r in fake.requests if r[1].endswith("/message"))
    assert prompt[2]["model"] == {"providerID": "openai", "modelID": "gpt-5"}
    assert prompt[2]["agent"] == "plan"


@pytest.mark.asyncio
async def test_create_session_returns_id() -> None:
    fake = FakeOpencode()
    assert await fake.client().create_session("My chat") == "ses_test"


@pytest.mark.asyncio
async def test_providers_normalized() -> None:
    fake = FakeOpencode()
    assert await fake.client().providers() == [
        {
            "id": "openai",
            "name": "OpenAI",
            "models": [
                {"id": "gpt-5", "name": "GPT-5", "supports_tools": True},
            ],
        }
    ]


def test_injected_endpoint_reports_running_and_skips_spawn() -> None:
    fake = FakeOpencode()
    client = fake.client()
    assert client.is_running() is True
    client.start()  # must be a no-op: no process spawned
    assert client._proc is None
    assert client.base_url == "http://fake-opencode"


def test_start_spawn_command_sources_workspace_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".env.remote").write_text("ANTHROPIC_API_KEY=secret\n")

    captured: dict[str, object] = {}

    class Proc:
        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> None:
            pass

        def kill(self) -> None:
            pass

    def fake_popen(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        return Proc()

    monkeypatch.setattr("desktop.core.opencode_client.subprocess.Popen", fake_popen)

    client = OpencodeClient(workdir=str(workspace), opencode_bin="opencode")

    def is_running(self: OpencodeClient) -> bool:
        return bool(captured.get("cmd"))

    monkeypatch.setattr(
        "desktop.core.opencode_client.OpencodeClient.is_running", is_running
    )

    client.start()
    assert captured["cwd"] == str(workspace)
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[0] == "bash"
    assert cmd[1] == "-lc"
    shell = cmd[2]
    assert "set -a" in shell
    assert ".env.remote" in shell
    assert ".env" in shell
    assert " serve --port " in shell


# -- pure helpers ------------------------------------------------------------


def test_model_payload_parsing() -> None:
    assert _model_payload("openai/gpt-5") == {
        "providerID": "openai",
        "modelID": "gpt-5",
    }
    assert _model_payload("anthropic/claude/x") == {
        "providerID": "anthropic",
        "modelID": "claude/x",
    }
    assert _model_payload("no-slash") is None
    assert _model_payload("") is None
    assert _model_payload(None) is None


def test_extract_session_error_shapes() -> None:
    assert _extract_session_error({"data": {"message": "boom"}}) == "boom"
    assert _extract_session_error({"name": "AuthError"}) == "AuthError"
    assert _extract_session_error({}) == ""
    assert _extract_session_error(None) == ""


def test_extract_text_joins_text_parts() -> None:
    payload = {
        "parts": [
            {"type": "text", "text": "a"},
            {"type": "tool"},
            {"type": "text", "text": "b"},
        ]
    }
    assert _extract_text(payload) == "a\nb"
    assert _extract_text({"message": {"parts": [{"type": "text", "text": "c"}]}}) == "c"
    assert _extract_text({}) == ""
