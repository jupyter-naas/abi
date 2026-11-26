"""A turn in a workspace limited to some models (``iam/workspace_models``), driven end
to end through ``stream_chat_response`` with fakes (as the slides tests do): the model
announced, handed to the provider and stored is one the conversation's workspace uses,
and an agent with a provider of its own on another model is refused."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary import (
    chat__primary_adapter__streaming as streaming,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (  # noqa: E501
    ChatRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__streaming_slides_test import (  # noqa: E501
    _Capture,
    _install_fakes,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import workspace_models
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_models import WorkspaceModels
from naas_abi_core.services.agent.context import agent_workspace_enabled_class_names

ONLY_QWEN = WorkspaceModels(frozenset({"qwen-3.8"}), "qwen-3.8")


@pytest.fixture(autouse=True)
def _usable_agents_bound():
    token = agent_workspace_enabled_class_names.set(frozenset())
    yield
    agent_workspace_enabled_class_names.reset(token)


async def _turn(monkeypatch, provider: dict[str, Any], llm_model: str | None) -> _Capture:
    capture = _Capture()
    _install_fakes(monkeypatch, capture)
    resolved = SimpleNamespace(
        id="p1",
        name="P",
        enabled=True,
        api_key=None,
        account_id=None,
        llm_model=None,
        run_workspace_id="ws-a",
        **provider,
    )

    async def fake_resolve_provider(*_args: Any, **_kwargs: Any):
        return resolved

    async def fake_turn_container(_workspace_id: str) -> str:
        return "abi:nexus:workspace/ws-a"

    async def models_of_workspace(workspace_id: str) -> WorkspaceModels:
        return ONLY_QWEN if workspace_id == "ws-a" else workspace_models.UNRESTRICTED

    async def fake_openai(_messages, config, _system):
        capture.llm_model = config.llm_model or config.model
        yield "ok"

    from contextlib import contextmanager

    faked = streaming.bind_registry

    @contextmanager
    def stored_in_ws_a(db):
        # The conversation is stored in ws-a: the turn's workspace (the request names
        # none, so the roster of a named workspace is not read).
        with faked(db) as registry:
            chat = registry.chat

            async def stored(**_kwargs):
                return SimpleNamespace(workspace_id="ws-a")

            chat.get_conversation_for_user = stored
            yield registry

    monkeypatch.setattr(streaming, "bind_registry", stored_in_ws_a)
    monkeypatch.setattr(streaming, "resolve_provider", fake_resolve_provider)
    monkeypatch.setattr(streaming, "turn_container", fake_turn_container)
    monkeypatch.setattr(workspace_models, "models_in_workspace", models_of_workspace)
    from naas_abi.apps.nexus.apps.api.app.services import provider_runtime

    monkeypatch.setattr(provider_runtime, "inprocess_agent_model_ids", lambda _name: {"gpt-x"})
    monkeypatch.setattr(provider_runtime, "stream_with_openai_compatible", fake_openai)
    request = ChatRequest(
        conversation_id="conv-1",
        workspace_id=None,
        message="hello",
        agent="abi",
        llm_model=llm_model,
    )
    response = await streaming.stream_chat_response(
        request=request, current_user=SimpleNamespace(id="user-1")
    )
    import json

    async for chunk in response.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
        for line in text.splitlines():
            payload = line.removeprefix("data: ").strip()
            if line.startswith("data: ") and payload != "[DONE]":
                try:
                    parsed = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    capture.frames.append(parsed)
    return capture


INPROCESS = {"type": "abi", "endpoint": "inprocess://abi", "model": "abi"}


@pytest.mark.asyncio
async def test_a_picked_model_the_workspace_does_not_offer_runs_on_its_default(monkeypatch):
    capture = await _turn(monkeypatch, INPROCESS, "gpt-x")
    assert capture.llm_model == "qwen-3.8"
    assert capture.frames[0]["llm_model"] == "qwen-3.8"
    assert capture.metadata is not None and capture.metadata["llm_model"] == "qwen-3.8"


@pytest.mark.asyncio
async def test_an_agent_on_a_model_not_offered_runs_on_the_default(monkeypatch):
    capture = await _turn(monkeypatch, INPROCESS, None)
    assert capture.llm_model == "qwen-3.8"
    assert capture.frames[0]["llm_model"] == "qwen-3.8"


@pytest.mark.asyncio
async def test_an_agent_with_a_provider_of_its_own_on_another_model_is_refused(monkeypatch):
    capture = await _turn(monkeypatch, {"type": "openai", "endpoint": None, "model": "gpt-x"}, None)
    assert capture.llm_model is None
    assert "not offered in this workspace" in capture.frames[0]["error"]
    allowed = await _turn(
        monkeypatch, {"type": "openai", "endpoint": None, "model": "qwen-3.8"}, None
    )
    assert allowed.llm_model == "qwen-3.8"
