"""Office slashes hand the turn to the office agent and do not inline a procedure."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary import (
    chat__primary_adapter__streaming as streaming,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest,
    MessageRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import Message
from naas_abi.apps.nexus.apps.api.app.services.skills.service import SkillService

_MARKERS = {
    "sheets": "The workbook JSON inside `workbook.html` is authoritative.",
    "slides": (
        "Hand the deck to SlidesAgent and write the open presentation HTML, "
        "not a PowerPoint file."
    ),
    "documents": (
        "Hand the memo to DocumentsAgent and fill the open document template "
        "instead of emitting a Word file."
    ),
    "web-research": (
        "Run search_public_web or web_search and cite only URLs the tool returned."
    ),
}


def _agent(
    agent_id: str,
    *,
    name: str,
    class_name: str,
    enabled: bool = True,
    is_default: bool = False,
) -> AgentRecord:
    base = datetime(2026, 7, 31, 10, 0, 0)
    return AgentRecord(
        id=agent_id,
        workspace_id="ws-1",
        name=name,
        description="",
        enabled=enabled,
        class_name=class_name,
        module_path=class_name.split("/", 1)[0],
        system_prompt=None,
        model_id=None,
        provider="abi",
        logo_url=None,
        created_at=base,
        updated_at=base + timedelta(seconds=1),
        is_default=is_default,
    )


def _roster(*, sheets: bool = True) -> list[AgentRecord]:
    agents = [
        _agent(
            "abi",
            name="Abi",
            class_name="naas_abi.agents.AbiAgent/AbiAgent",
            is_default=True,
        ),
        _agent(
            "slides",
            name="Slides",
            class_name="naas_abi.agents.SlidesAgent/SlidesAgent",
        ),
        _agent(
            "documents",
            name="Documents",
            class_name="naas_abi.agents.DocumentsAgent/DocumentsAgent",
        ),
    ]
    if sheets:
        agents.append(
            _agent(
                "sheets",
                name="Sheets",
                class_name="naas_abi.agents.SheetsAgent/SheetsAgent",
            )
        )
    return agents


def _context() -> RequestContext:
    return RequestContext(
        token_data=TokenData(user_id="user-1", scopes={"*"}, is_authenticated=True)
    )


def _chat(tmp_path) -> ChatService:
    adapter = AsyncMock()
    adapter.list_visible = AsyncMock(return_value=[])
    service = SkillService(adapter, user_skills_root=tmp_path)
    service._ensure_workspace_access = AsyncMock()  # type: ignore[method-assign]
    return ChatService(adapter=SimpleNamespace(), skills_service=service)


def test_open_workbook_keeps_the_sheets_agent_and_slash_does_not_override_a_deck() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.chat.office_handoff import (
        resolve_workspace_turn_agent,
        suppressed_office_skill_slug,
    )

    agents = _roster()
    assert (
        resolve_workspace_turn_agent(
            agents,
            "abi",
            "update A1",
            {"sheets": {"slug": "budget"}},
        )
        == "sheets"
    )
    assert (
        resolve_workspace_turn_agent(
            agents,
            "abi",
            "/sheets budget",
            {"slides": {"slug": "q3"}},
        )
        == "slides"
    )
    assert suppressed_office_skill_slug(agents, "/sheets budget") == "sheets"
    assert suppressed_office_skill_slug(_roster(sheets=False), "/sheets budget") is None


def test_office_slash_selects_the_office_agent_when_no_file_is_open() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.chat.office_handoff import (
        resolve_workspace_turn_agent,
        suppressed_office_skill_slug,
    )

    agents = _roster()
    assert resolve_workspace_turn_agent(agents, "abi", "/sheets budget") == "sheets"
    assert resolve_workspace_turn_agent(agents, "abi", "/slides a deck") == "slides"
    assert resolve_workspace_turn_agent(agents, "abi", "/documents a memo") == "documents"
    assert resolve_workspace_turn_agent(agents, "abi", "/web-research wheat") == "abi"
    assert suppressed_office_skill_slug(agents, "/web-research wheat") is None
    assert (
        resolve_workspace_turn_agent(_roster(sheets=False), "abi", "/sheets budget")
        == "abi"
    )


@pytest.mark.asyncio
async def test_catalog_lists_office_rows_without_bodies_and_follow_up_omits_it(
    tmp_path,
) -> None:
    chat = _chat(tmp_path)
    context = _context()
    block = await chat._build_skills_block(context, "ws-1", [])
    assert "slug: sheets" in block
    assert "name: Sheets" in block
    assert "description: Spreadsheet work in Nexus Sheets." in block
    assert "when_to_use: The user wants a spreadsheet" in block
    assert "/sheets, /slides, and /documents hand the turn" in block
    for marker in _MARKERS.values():
        assert marker not in block

    follow = await chat._build_skills_block(
        context,
        "ws-1",
        [SimpleNamespace(role="assistant", content="Hello")],
    )
    assert "slug: sheets" not in follow
    assert "when_to_use:" not in follow
    assert "Available skills" not in follow
    for marker in _MARKERS.values():
        assert marker not in follow


@pytest.mark.asyncio
async def test_web_research_still_expands_and_office_slash_does_not_when_handed_off(
    tmp_path,
) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.chat.office_handoff import (
        suppressed_office_skill_slug,
    )

    chat = _chat(tmp_path)
    context = _context()
    agents = _roster()

    research = await chat.expand_invoked_skill_messages(
        [Message(role="user", content="/web-research the price of wheat")],
        context,
        "ws-1",
        suppress_slugs=set(),
    )
    assert _MARKERS["web-research"] in research[0].content

    for slug in ("sheets", "slides", "documents"):
        message = f"/{slug} build it"
        suppress = suppressed_office_skill_slug(agents, message)
        assert suppress == slug
        expanded = await chat.expand_invoked_skill_messages(
            [Message(role="user", content=message)],
            context,
            "ws-1",
            suppress_slugs={suppress},
        )
        assert expanded[0].content == message
        assert _MARKERS[slug] not in expanded[0].content
        assert "Invoked skill" not in expanded[0].content

    fallback = await chat.expand_invoked_skill_messages(
        [Message(role="user", content="/sheets budget")],
        context,
        "ws-1",
        suppress_slugs=set(),
    )
    assert _MARKERS["sheets"] in fallback[0].content


def _install_stream_fakes(
    monkeypatch: pytest.MonkeyPatch,
    capture: dict[str, Any],
    roster: list[AgentRecord],
    chat: ChatService,
) -> None:
    provider = SimpleNamespace(
        id="p1",
        name="Abi",
        type="abi",
        enabled=True,
        endpoint="inprocess://abi",
        api_key=None,
        account_id=None,
        model="naas_abi.agents.AbiAgent/AbiAgent",
        llm_model="gpt-4.1-mini",
    )

    async def fake_resolve_provider(*args: Any, **_kwargs: Any):
        capture["agent_id"] = args[3] if len(args) > 3 else None
        return provider

    @asynccontextmanager
    async def fake_session():
        db = SimpleNamespace()

        async def _noop() -> None:
            return None

        db.commit = _noop
        db.rollback = _noop
        yield db

    async def list_workspace_agents(*_args: Any, **_kwargs: Any):
        return roster

    class _FakeChat:
        def _inject_chat_vector_context(self, provider_messages, **_kwargs):
            return provider_messages, []

        async def expand_invoked_skill_messages(self, messages, *args, **kwargs):
            return await chat.expand_invoked_skill_messages(messages, *args, **kwargs)

        async def build_system_prompt(self, **kwargs):
            return await chat.build_system_prompt(**kwargs)

        async def build_abi_injection_preamble(self, **kwargs):
            return await chat.build_abi_injection_preamble(**kwargs)

        async def create_streaming_message_pair(self, **kwargs):
            capture["assistant_agent"] = kwargs.get("assistant_agent")
            return None, "assistant-msg-1"

    @contextmanager
    def fake_bind_registry(_db):
        yield SimpleNamespace(
            agents=SimpleNamespace(list_workspace_agents=list_workspace_agents),
            chat=_FakeChat(),
        )

    async def fake_get_or_create_conversation(**_kwargs) -> str:
        return "conv-1"

    async def fake_build_provider_messages(**kwargs) -> list[Any]:
        request = kwargs.get("request")
        text = getattr(request, "message", "") if request is not None else ""
        return [Message(role="user", content=text)]

    async def fake_persist_stream_content(**_kwargs) -> None:
        return None

    async def fake_persist_stream_metadata(**_kwargs) -> None:
        return None

    async def fake_stream(messages, _config, **kwargs):
        capture["messages"] = messages
        capture["preamble"] = kwargs.get("user_context_preamble")
        yield "ok"

    monkeypatch.setattr(streaming, "resolve_provider", fake_resolve_provider)
    monkeypatch.setattr(streaming, "AsyncSessionLocal", fake_session)
    monkeypatch.setattr(streaming, "bind_registry", fake_bind_registry)
    monkeypatch.setattr(streaming, "get_or_create_conversation", fake_get_or_create_conversation)
    monkeypatch.setattr(streaming, "build_provider_messages_with_agents", fake_build_provider_messages)
    monkeypatch.setattr(streaming, "request_context", lambda _user: _context())
    monkeypatch.setattr(streaming, "persist_stream_content", fake_persist_stream_content)
    monkeypatch.setattr(streaming, "persist_stream_metadata", fake_persist_stream_metadata)
    monkeypatch.setattr(streaming, "stream_with_abi_inprocess", fake_stream)


async def _drive(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    *,
    roster: list[AgentRecord],
    chat: ChatService,
    context: dict | None = None,
) -> dict[str, Any]:
    capture: dict[str, Any] = {}
    _install_stream_fakes(monkeypatch, capture, roster, chat)
    request = ChatRequest(
        conversation_id="conv-1",
        workspace_id="ws-1",
        message=message,
        agent="abi",
        messages=[MessageRequest(role="user", content=message)],
        context=context,
    )
    response = await streaming.stream_chat_response(
        request=request,
        current_user=SimpleNamespace(id="user-1"),
    )
    frames: list[dict[str, Any]] = []
    async for chunk in response.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
        for line in text.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: ") :].strip()
            if payload == "[DONE]":
                continue
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                frames.append(parsed)
    capture["frames"] = frames
    return capture


def _provider_text(capture: dict[str, Any]) -> str:
    messages = capture.get("messages") or []
    body = "\n".join(getattr(message, "content", "") for message in messages)
    return f"{capture.get('preamble') or ''}\n{body}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "context", "agent_id", "slug"),
    [
        ("/sheets budget", None, "sheets", "sheets"),
        ("/slides a deck", None, "slides", "slides"),
        ("/documents a memo", None, "documents", "documents"),
        ("/sheets budget", {"sheets": {"slug": "budget"}}, "sheets", "sheets"),
        ("/sheets budget", {"slides": {"slug": "q3"}}, "slides", "sheets"),
    ],
)
async def test_office_slash_hands_off_without_inlining_the_procedure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    message: str,
    context: dict | None,
    agent_id: str,
    slug: str,
) -> None:
    capture = await _drive(
        monkeypatch,
        message,
        roster=_roster(),
        chat=_chat(tmp_path),
        context=context,
    )
    errors = [frame.get("error") for frame in capture["frames"] if frame.get("error")]
    assert not errors, errors
    assert capture["agent_id"] == agent_id
    assert capture["assistant_agent"] == agent_id
    text = _provider_text(capture)
    assert _MARKERS[slug] not in text
    assert "Invoked skill" not in text
    assert "slug: sheets" in (capture.get("preamble") or "")
    assert "when_to_use:" in (capture.get("preamble") or "")


@pytest.mark.asyncio
async def test_web_research_slash_stays_on_the_current_agent_and_expands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    capture = await _drive(
        monkeypatch,
        "/web-research the price of wheat",
        roster=_roster(),
        chat=_chat(tmp_path),
    )
    errors = [frame.get("error") for frame in capture["frames"] if frame.get("error")]
    assert not errors, errors
    assert capture["agent_id"] == "abi"
    text = _provider_text(capture)
    assert _MARKERS["web-research"] in text
    assert "Invoked skill /web-research" in text


@pytest.mark.asyncio
async def test_missing_sheets_agent_keeps_slash_expansion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    capture = await _drive(
        monkeypatch,
        "/sheets budget",
        roster=_roster(sheets=False),
        chat=_chat(tmp_path),
    )
    errors = [frame.get("error") for frame in capture["frames"] if frame.get("error")]
    assert not errors, errors
    assert capture["agent_id"] == "abi"
    assert _MARKERS["sheets"] in _provider_text(capture)
