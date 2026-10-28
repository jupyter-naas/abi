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
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.openai_gateway.adapters.primary import (
    openai_gateway__primary_adapter__FastAPI as shim,
)

_AIA_KEY = "naas_abi.agents.AiaAgent/AiaAgent"
_AIA = ModuleScope("agent", "naas_abi", "Aia")
_SUPPORT = ModuleScope("agent", "naas_abi", "Support")


def _client(monkeypatch: pytest.MonkeyPatch, user_id: str = "admin") -> TestClient:
    app = FastAPI()
    app.include_router(shim.router, prefix="/v1")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=user_id, email="user@example.com", name="User One"
    )

    async def _fake_stream(
        model: str,
        messages: object,
        thread_id: str,
        ws_base: str | None = None,
        ws_secret: str | None = None,
        user_context_preamble: str | None = None,
        allowed: frozenset[str] | None = None,
        processes: frozenset[tuple[str, str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        STREAMED.append(allowed)
        PROCESSES.append(processes)
        for piece in ["Hello", " world"]:
            yield piece

    STREAMED.clear()
    PROCESSES.clear()
    # This engine has no module workflows (the class registry is process-wide).
    from naas_abi.apps.nexus.apps.api.app.services.agents import scopes as agent_scopes

    monkeypatch.setattr(agent_scopes, "engine_process_scopes", lambda: [])
    aia = type("AiaAgent", (), {"name": "Aia"})
    monkeypatch.setattr(shim, "_stream_agent_text", _fake_stream)
    monkeypatch.setattr(shim, "_list_agent_model_ids", lambda: ["aia", "support"])
    monkeypatch.setattr(shim, "_model_scopes", lambda: {"aia": _AIA, "support": _SUPPORT})
    monkeypatch.setattr(
        shim,
        "_agent_scope_of",
        lambda model: (_AIA_KEY, _AIA) if model == "aia" else None,
    )
    monkeypatch.setattr(shim, "_agent_classes", lambda: ({_AIA_KEY: aia}, {_AIA_KEY: "naas_abi"}))
    return TestClient(app)


PROCESSES: list = []
STREAMED: list[frozenset[str] | None] = []


def test_models(team: NexusIam, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.get("/v1/models")
    assert resp.status_code == 200, resp.text
    ids = [m["id"] for m in resp.json()["data"]]
    assert "aia" in ids


def test_chat_completion_non_streaming(team: NexusIam, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_chat_completion_streaming(team: NexusIam, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_gateway_turn_carries_the_caller_profile_onto_the_agent_prompt(
    team: NexusIam,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The profile has to arrive on the prompt the agent actually runs.

    ABI agents build their own system prompt, so prepending to the latest user
    message is the only channel that reaches them. Nexus uses it; this gateway
    called ``stream_with_abi_inprocess`` with three positional arguments and
    never named the fourth, so every turn from an OpenAI-compatible client ran
    with no idea who it was acting for.

    Read off a fake agent rather than off the call, because a test that
    asserts the gateway passes an argument passes just as well when the
    argument is dropped one frame later.
    """

    class _Agent:
        """Enough of ``Agent.stream_invoke`` to be driven for real.

        The closing ``done`` event is not decoration: ``stream_with_abi_inprocess``
        pumps this generator with ``asyncio.to_thread(next, ...)``, and a
        ``StopIteration`` cannot be set on a future, so a double that ends by
        running out hangs the request instead of finishing it.
        """

        def __init__(self) -> None:
            self.prompt: str | None = None

        def stream_invoke(self, prompt: str):
            self.prompt = prompt
            yield {"event": "ai_message", "data": "answer"}
            yield {"event": "done", "data": "[DONE]"}

    agent = _Agent()
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.provider_runtime._resolve_inprocess_abi_agent",
        lambda _model: agent,
    )
    key = f"{_Agent.__module__}/{_Agent.__name__}"
    monkeypatch.setattr(shim, "_agent_classes", lambda: ({key: _Agent}, {key: "naas_abi"}))

    app = FastAPI()
    app.include_router(shim.router, prefix="/v1")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="admin",
        email="user@example.com",
        name="User One",
        organization="NaasAI",
        job_title="CTO",
        bio=None,
    )

    resp = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "aia", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 200, resp.text
    assert agent.prompt is not None
    assert "User One" in agent.prompt
    assert "user@example.com" in agent.prompt
    assert agent.prompt.endswith("hi")


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


_COMPLETION = {"model": "aia", "messages": [{"role": "user", "content": "hi"}]}


@pytest.mark.parametrize("user", ["admin", "owner"])
def test_admins_and_owners_use_every_agent(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch, user: str
) -> None:
    client = _client(monkeypatch, user)

    assert [m["id"] for m in client.get("/v1/models").json()["data"]] == ["aia", "support"]
    assert client.post("/v1/chat/completions", json=_COMPLETION).status_code == 200
    # The agent reaches the sub-agents the caller may use there.
    assert STREAMED == [frozenset({_AIA_KEY})]
    # And the module workflows its tools may run there (this engine has none).
    assert PROCESSES == [frozenset()]


@pytest.mark.parametrize("user", ["viewer", "member"])
def test_viewers_and_members_use_no_agent_by_default(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch, user: str
) -> None:
    client = _client(monkeypatch, user)

    assert client.get("/v1/models").json()["data"] == []
    assert client.post("/v1/chat/completions", json=_COMPLETION).status_code == 403


def test_a_member_granted_one_agent_lists_and_uses_that_one(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch
) -> None:
    team.allow_scope("member", _AIA, "abi:org-1:ws-1")
    client = _client(monkeypatch, "member")

    assert [m["id"] for m in client.get("/v1/models").json()["data"]] == ["aia"]
    assert client.post("/v1/chat/completions", json=_COMPLETION).status_code == 200
    support = {**_COMPLETION, "model": "support"}
    monkeypatch.setattr(shim, "_agent_scope_of", lambda model: ("naas_abi.agents.S/S", _SUPPORT))
    assert client.post("/v1/chat/completions", json=support).status_code == 403


def test_an_unknown_model_is_not_found(team: NexusIam, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)

    assert (
        client.post("/v1/chat/completions", json={**_COMPLETION, "model": "x"}).status_code == 404
    )


def test_a_user_with_no_workspace_may_not_use_the_gateway(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(monkeypatch, "stranger")

    assert client.get("/v1/models").status_code == 403
    assert client.post("/v1/chat/completions", json=_COMPLETION).status_code == 403
    assert (
        client.post("/v1/chat/completions", json={**_COMPLETION, "stream": True}).status_code == 403
    )


def test_a_workspace_named_by_the_client_is_the_one_that_decides(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch
) -> None:
    team.workspace("org-1", "ws-2")
    team.allow_scope("member", _AIA, "abi:org-1:ws-1")
    client = _client(monkeypatch, "member")

    assert (
        client.post("/v1/chat/completions?workspace_id=ws-1", json=_COMPLETION).status_code == 200
    )
    assert (
        client.post("/v1/chat/completions?workspace_id=ws-2", json=_COMPLETION).status_code == 403
    )
    assert client.get("/v1/models?workspace_id=ws-2").status_code == 403


def test_the_gateway_needs_the_chat_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    flags = FeatureFlagsConfig(
        enabled_features=["files"], role_baseline={"owner": ["files"], "member": ["files"]}
    )
    nexus = NexusIam(flags)
    nexus.grant("member", "member", nexus.workspace("org-1", "ws-1"))

    with nexus.installed():
        client = _client(monkeypatch, "member")

        assert client.get("/v1/models").status_code == 403
        assert client.post("/v1/chat/completions", json=_COMPLETION).status_code == 403
