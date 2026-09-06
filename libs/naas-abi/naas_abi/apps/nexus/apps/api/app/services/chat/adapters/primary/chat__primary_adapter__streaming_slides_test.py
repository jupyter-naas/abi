"""Call-site coverage for the slides model override in the streaming adapter.

The policy unit tests in ``slides_policy_test.py`` already pass, so they cannot
catch the adapter handing the policy too few arguments. These tests drive
``stream_chat_response`` end to end with fakes and assert on the model that
actually reaches the provider, which is the only thing the user experiences.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi.agents.slides_policy import configured_slides_model
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary import (
    chat__primary_adapter__streaming as streaming,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest,
)
from naas_abi_core.services.agent.context import (
    slides_active_slug,
    slides_creation_intent,
    slides_research_queries,
    slides_research_required,
)

WEAK_MODEL = "gpt-4.1-mini"


@pytest.fixture(autouse=True)
def _reset_slides_context():
    tokens = [
        (slides_active_slug, slides_active_slug.set("")),
        (slides_creation_intent, slides_creation_intent.set(False)),
        (slides_research_required, slides_research_required.set(False)),
        (slides_research_queries, slides_research_queries.set(None)),
    ]
    yield
    for var, token in tokens:
        var.reset(token)


class _Capture:
    """Records what the adapter handed the provider for this turn."""

    def __init__(self) -> None:
        self.llm_model: str | None = None
        self.metadata: dict[str, Any] | None = None


def _install_fakes(monkeypatch: pytest.MonkeyPatch, capture: _Capture) -> None:
    provider = SimpleNamespace(
        id="p1",
        name="Abi",
        type="abi",
        enabled=True,
        endpoint=None,
        api_key=None,
        account_id=None,
        model="abi",
        llm_model=WEAK_MODEL,
    )

    async def fake_resolve_provider(*_args: Any, **_kwargs: Any):
        return provider

    @asynccontextmanager
    async def fake_session():
        db = SimpleNamespace()

        async def _noop() -> None:
            return None

        db.commit = _noop
        db.rollback = _noop
        yield db

    class _FakeChat:
        def _inject_chat_vector_context(self, provider_messages, **_kwargs):
            return provider_messages, []

        async def build_system_prompt(self, **_kwargs) -> str:
            return "system"

        async def build_abi_injection_preamble(self, **_kwargs) -> None:
            return None

        async def create_streaming_message_pair(self, **_kwargs):
            return None, "assistant-msg-1"

    @contextmanager
    def fake_bind_registry(_db):
        yield SimpleNamespace(chat=_FakeChat())

    async def fake_get_or_create_conversation(**_kwargs) -> str:
        return "conv-1"

    async def fake_build_provider_messages(**_kwargs) -> list[Any]:
        return []

    async def fake_persist_stream_content(**_kwargs) -> None:
        return None

    async def fake_persist_stream_metadata(**_kwargs) -> None:
        capture.metadata = _kwargs.get("metadata")

    async def fake_stream_with_abi_inprocess(_messages, config, **_kwargs):
        capture.llm_model = config.llm_model
        yield "ok"

    monkeypatch.setattr(streaming, "resolve_provider", fake_resolve_provider)
    monkeypatch.setattr(streaming, "AsyncSessionLocal", fake_session)
    monkeypatch.setattr(streaming, "bind_registry", fake_bind_registry)
    monkeypatch.setattr(streaming, "get_or_create_conversation", fake_get_or_create_conversation)
    monkeypatch.setattr(
        streaming, "build_provider_messages_with_agents", fake_build_provider_messages
    )
    monkeypatch.setattr(streaming, "request_context", lambda user: SimpleNamespace(user=user))
    monkeypatch.setattr(streaming, "persist_stream_content", fake_persist_stream_content)
    monkeypatch.setattr(streaming, "persist_stream_metadata", fake_persist_stream_metadata)
    monkeypatch.setattr(streaming, "stream_with_abi_inprocess", fake_stream_with_abi_inprocess)


async def _run_turn(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    context: dict[str, Any] | None = None,
) -> _Capture:
    capture = _Capture()
    _install_fakes(monkeypatch, capture)
    request = ChatRequest(
        conversation_id="conv-1",
        workspace_id=None,
        message=message,
        agent="abi",
        llm_model=WEAK_MODEL,
        context=context,
    )
    response = await streaming.stream_chat_response(
        request=request,
        current_user=SimpleNamespace(id="user-1"),
    )
    async for _chunk in response.body_iterator:
        pass
    return capture


@pytest.mark.asyncio
async def test_french_deck_request_from_main_chat_upgrades_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The turn that writes the whole deck must not run on a mini model.

    Creating a deck from the main chat is a supported flow, so no deck is open
    yet and ``client_context`` carries no slug. The user brief is the only
    signal available, and the adapter has to pass it to the policy.
    """
    capture = await _run_turn(
        monkeypatch,
        "Fais-moi une présentation sur la souveraineté numérique européenne",
    )
    assert capture.llm_model == configured_slides_model()


@pytest.mark.asyncio
async def test_english_deck_request_from_main_chat_upgrades_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = await _run_turn(
        monkeypatch,
        "create a deck on the latest developments in EU chip policy",
    )
    assert capture.llm_model == configured_slides_model()


@pytest.mark.asyncio
async def test_open_deck_still_upgrades_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = await _run_turn(
        monkeypatch,
        "ajoute une slide sur les risques",
        context={"slides": {"slug": "souverainete-numerique"}},
    )
    assert capture.llm_model == configured_slides_model()


@pytest.mark.asyncio
async def test_persisted_metadata_reports_the_model_actually_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chat footer renders this field, so it must not echo the request.

    Persisting the incoming selection makes the UI claim GPT-4.1 Mini while the
    deck is really being written by the slides model, which is how the
    downgrade stayed invisible.
    """
    capture = await _run_turn(
        monkeypatch,
        "Fais-moi un deck sur la situation au Sahel",
    )
    assert capture.metadata is not None
    assert capture.metadata["llm_model"] == configured_slides_model()


@pytest.mark.asyncio
async def test_ordinary_question_keeps_the_selected_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard against over-triggering: a plain chat turn must be left alone."""
    capture = await _run_turn(monkeypatch, "combien font 2 + 2 ?")
    assert capture.llm_model == WEAK_MODEL
