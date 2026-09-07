from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.openai_gateway.adapters.primary import (
    openai_gateway__primary_adapter__FastAPI as shim,
)


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(shim.router, prefix="/v1")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="user@example.com", name="User One"
    )

    async def _fake_stream(
        model: str,
        messages: object,
        thread_id: str,
        ws_base: str | None = None,
        ws_secret: str | None = None,
    ) -> AsyncGenerator[str, None]:
        for piece in ["Hello", " world"]:
            yield piece

    monkeypatch.setattr(shim, "_stream_agent_text", _fake_stream)
    monkeypatch.setattr(shim, "_list_agent_model_ids", lambda: ["aia", "support"])
    return TestClient(app)


def test_models(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.get("/v1/models")
    assert resp.status_code == 200, resp.text
    ids = [m["id"] for m in resp.json()["data"]]
    assert "aia" in ids


def test_chat_completion_non_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "aia", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200, resp.text
    content = resp.json()["choices"][0]["message"]["content"]
    # the reply carries a hidden chat-id marker; the visible text is the answer
    assert shim._CHAT_MARKER_RE.search(content)
    assert shim._CHAT_MARKER_RE.sub("", content).strip() == "Hello world"


def test_chat_completion_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "aia",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 200
    body = resp.text
    assert "data: [DONE]" in body
    contents: list[str] = []
    for line in body.splitlines():
        if line.startswith("data: ") and "[DONE]" not in line:
            payload = json.loads(line[len("data: ") :])
            delta = payload["choices"][0]["delta"]
            if "content" in delta:
                contents.append(delta["content"])
    joined = "".join(contents)
    assert shim._CHAT_MARKER_RE.search(joined)
    assert shim._CHAT_MARKER_RE.sub("", joined).strip() == "Hello world"


def test_format_tool_event_renders_calls_and_results() -> None:
    # tool call -> a visible markdown header with the tool name
    call = shim._format_tool_event({"event": "tool_usage", "tool": "kg_sparql_query"})
    assert "kg_sparql_query" in call and "🔧" in call
    # tool result -> a fenced code block with the output
    resp = shim._format_tool_event({"event": "tool_response", "output": "42 rows"})
    assert "```" in resp and "42 rows" in resp
    # long output is truncated
    big = shim._format_tool_event({"event": "tool_response", "output": "x" * 5000})
    assert "truncated" in big and len(big) < 1200
    # empty / unrelated events render nothing
    assert shim._format_tool_event({"event": "tool_usage", "tool": ""}) == ""
    assert shim._format_tool_event({"event": "call_model", "agent": "AbiAgent"}) == ""
