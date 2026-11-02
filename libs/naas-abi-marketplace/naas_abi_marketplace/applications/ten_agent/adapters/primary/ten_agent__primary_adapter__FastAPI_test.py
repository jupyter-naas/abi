from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi_marketplace.applications.ten_agent.adapters.primary.ten_agent__primary_adapter__FastAPI import (
    build_router,
)
from naas_abi_marketplace.applications.ten_agent.domain.ports import (
    AgentMessage,
    AgentStreamPort,
)


class _FakeAbi(AgentStreamPort):
    """Streams what an ABI agent streams: tool events, then markdown."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def stream(
        self,
        agent: str,
        messages: list[AgentMessage],
        thread_id: str,
        preamble: str | None,
    ) -> AsyncIterator[str | dict[str, Any]]:
        self.calls.append(
            {
                "agent": agent,
                "messages": messages,
                "thread_id": thread_id,
                "preamble": preamble,
            }
        )
        chunks: list[str | dict[str, Any]] = [
            {"event": "tool_usage", "tool": "kg_sparql_query"},
            {"event": "tool_response", "output": "```\n42 rows\n```"},
            "You have **42** contacts.",
            " See [the list](https://x.io). <!-- abi-chat:0123abcd -->",
        ]
        for chunk in chunks:
            yield chunk


USER = SimpleNamespace(
    id="user-1",
    name="Ada Lovelace",
    email="ada@example.com",
    organization=None,
    job_title=None,
    bio=None,
)


def _client() -> tuple[TestClient, _FakeAbi]:
    abi = _FakeAbi()
    app = FastAPI()
    app.include_router(
        build_router(abi, auth=lambda: USER),
        prefix="/api/v1/voice",
    )
    return TestClient(app), abi


def _post(
    client: TestClient, *, stream: bool, session: str | None = "call-7", messages=None
):
    headers = {"X-Voice-Session": session} if session else {}
    return client.post(
        "/api/v1/voice/chat/completions",
        headers=headers,
        json={
            "model": "AbiAgent",
            "stream": stream,
            "messages": messages or [{"role": "user", "content": "how many contacts?"}],
        },
    )


def _streamed(body: str) -> str:
    parts = []
    for line in body.splitlines():
        if line.startswith("data: ") and "[DONE]" not in line:
            parts.append(json.loads(line[6:])["choices"][0]["delta"].get("content", ""))
    return "".join(parts)


def test_streams_only_speakable_sentences() -> None:
    client, _ = _client()
    resp = _post(client, stream=True)
    assert resp.status_code == 200, resp.text
    assert resp.text.rstrip().endswith("data: [DONE]")
    text = _streamed(resp.text)
    assert text == "One moment, let me check. You have 42 contacts. See the list. "
    for noise in ("```", "**", "http", "abi-chat", "42 rows"):
        assert noise not in text


def test_non_streaming_reply_for_a_realtime_tool_call() -> None:
    client, _ = _client()
    content = _post(client, stream=False).json()["choices"][0]["message"]["content"]
    assert content == "One moment, let me check. You have 42 contacts. See the list."


def test_one_call_keeps_one_thread_scoped_to_the_user() -> None:
    client, abi = _client()
    _post(client, stream=False)
    _post(client, stream=False)
    assert (
        abi.calls[0]["thread_id"] == abi.calls[1]["thread_id"] == "voice-user-1-call-7"
    )


def test_every_turn_carries_the_voice_style_and_only_the_agent_named() -> None:
    client, abi = _client()
    _post(
        client,
        stream=False,
        messages=[
            {"role": "developer", "content": "be brief"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "hello"},
        ],
    )
    call = abi.calls[0]
    assert call["agent"] == "AbiAgent"
    assert call["preamble"].startswith("You are speaking on a live voice call.")
    assert [m.role for m in call["messages"]] == ["system", "assistant", "user"]
    assert "Ada Lovelace" not in call["preamble"]


def test_first_turn_tells_the_agent_who_is_calling() -> None:
    client, abi = _client()
    _post(client, stream=False)
    assert "Ada Lovelace" in abi.calls[0]["preamble"]


def test_rejects_callers_without_credentials() -> None:
    abi = _FakeAbi()
    app = FastAPI()
    app.include_router(build_router(abi, auth=None), prefix="/api/v1/voice")
    resp = _post(TestClient(app), stream=False)
    assert resp.status_code == 401
    assert abi.calls == []
