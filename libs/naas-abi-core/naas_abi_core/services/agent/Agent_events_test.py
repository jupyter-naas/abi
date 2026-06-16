# mypy: disable-error-code="arg-type,misc"
"""Tests for Agent's EventService publishing + identity ContextVars.

These tests exercise the publishing hooks (`_notify_*` and the
`AgentInvocationCompleted` emission) directly with a stub Agent — building a
real Agent requires a live chat model. The point of these tests is the wiring
(event-service discovery + identity stamping), not LangGraph orchestration.
"""

from __future__ import annotations

from contextvars import copy_context
from threading import Thread
from types import SimpleNamespace
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from naas_abi_core.engine.context import _event_service_override
from naas_abi_core.services.agent.Agent import Agent
from naas_abi_core.services.agent.context import (
    agent_chat_id,
    agent_user_id,
    agent_workspace_id,
)
from naas_abi_core.services.agent.ontologies.modules.AgentEventOntology import (
    AgentAIMessageEmitted,
    AgentInvocationCompleted,
    AgentModelCalled,
    AgentRouted,
    AgentToolCalled,
    AgentToolResponded,
    AgentUserMessageReceived,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeEventService:
    def __init__(self) -> None:
        self.published: list[Any] = []

    def publish(self, event: Any) -> None:
        self.published.append(event)


class _StubAgent:
    """An Agent-shaped object that only exposes what _notify_* + _identity need.

    We use this instead of a real Agent because Agent.__init__ requires a live
    chat model + langgraph compilation, which is far too much surface for this
    wiring test.
    """

    def __init__(self, name: str = "tester", thread_id: str = "t-1") -> None:
        self._name = name
        self._event_queue = SimpleNamespace(put=lambda _: None)
        self._on_tool_usage = lambda _: None
        self._on_tool_response = lambda _: None
        self._on_ai_message = lambda _, __: None
        self._on_call_model = lambda _: None
        self._on_agent_routing = lambda _: None
        self._state = SimpleNamespace(thread_id=thread_id)

    # Bind the real methods so we exercise the actual publishing code paths.
    _identity = Agent._identity
    _publish_agent_event = Agent._publish_agent_event
    _stringify_content = Agent._stringify_content
    _notify_tool_usage = Agent._notify_tool_usage
    _notify_tool_response = Agent._notify_tool_response
    _notify_ai_message = Agent._notify_ai_message
    _notify_call_model = Agent._notify_call_model
    _notify_agent_routing = Agent._notify_agent_routing


def _with_event_service(events: _FakeEventService | None):
    """Install `events` as the override EventService; return token for reset."""
    return _event_service_override.set(events)


# ---------------------------------------------------------------------------
# Discovery + no-op behaviour
# ---------------------------------------------------------------------------


def test_no_event_service_is_silent_noop() -> None:
    token = _with_event_service(None)
    try:
        _StubAgent()._notify_call_model("tester")  # must not raise
    finally:
        _event_service_override.reset(token)


def test_content_to_text_ignores_bedrock_internal_blocks() -> None:
    content = [
        {
            "type": "reasoning_content",
            "reasoning_content": {"text": "private reasoning", "signature": ""},
        },
        {
            "type": "tool_use",
            "name": "find_top_liked_tweets",
            "input": {"limit": "10"},
            "id": "tooluse_1",
        },
    ]

    assert Agent._content_to_text(content) == ""


def test_content_to_text_keeps_visible_text_blocks() -> None:
    content = [
        {
            "type": "reasoning_content",
            "reasoning_content": {"text": "private reasoning", "signature": ""},
        },
        {"type": "text", "text": "Visible answer"},
    ]

    assert Agent._content_to_text(content) == "Visible answer"


def test_has_tool_calls_reads_ai_message_tool_calls() -> None:
    message = AIMessage(
        content=[
            {
                "type": "tool_use",
                "name": "search",
                "input": {"query": "hello"},
                "id": "call-1",
            }
        ],
        tool_calls=[{"name": "search", "id": "call-1", "args": {"query": "hello"}}],
    )

    assert Agent._has_tool_calls(message) is True


def test_publisher_failure_does_not_break_notification() -> None:
    class _Exploding:
        def publish(self, _):
            raise RuntimeError("event bus down")

    token = _with_event_service(_Exploding())
    try:
        _StubAgent()._notify_call_model("tester")  # must swallow + log
    finally:
        _event_service_override.reset(token)


# ---------------------------------------------------------------------------
# Identity tagging
# ---------------------------------------------------------------------------


def test_chat_id_falls_back_to_thread_id_when_contextvar_unset() -> None:
    events = _FakeEventService()
    token = _with_event_service(events)
    try:
        _StubAgent(thread_id="thread-42")._notify_call_model("tester")
        evt = events.published[0]
        assert isinstance(evt, AgentModelCalled)
        assert evt.chat_id == "thread-42"
        assert evt.user_id is None
        assert evt.workspace_id is None
    finally:
        _event_service_override.reset(token)


def test_identity_contextvars_are_stamped_on_events() -> None:
    events = _FakeEventService()
    tokens = [
        _with_event_service(events),
        agent_user_id.set("alice"),
        agent_chat_id.set("chat-7"),
        agent_workspace_id.set("ws-9"),
    ]
    try:
        _StubAgent()._notify_call_model("tester")
        evt = events.published[0]
        assert evt.user_id == "alice"
        assert evt.chat_id == "chat-7"
        assert evt.workspace_id == "ws-9"
    finally:
        agent_workspace_id.reset(tokens[3])
        agent_chat_id.reset(tokens[2])
        agent_user_id.reset(tokens[1])
        _event_service_override.reset(tokens[0])


def test_contextvars_propagate_across_threads_with_copy_context() -> None:
    events = _FakeEventService()
    tokens = [_with_event_service(events), agent_user_id.set("bob")]
    try:
        def worker():
            _StubAgent()._notify_call_model("tester")

        ctx = copy_context()
        thread = Thread(target=ctx.run, args=(worker,))
        thread.start()
        thread.join()

        assert events.published[0].user_id == "bob"
    finally:
        agent_user_id.reset(tokens[1])
        _event_service_override.reset(tokens[0])


# ---------------------------------------------------------------------------
# Per-notification event shape
# ---------------------------------------------------------------------------


def test_notify_tool_usage_emits_one_event_per_tool_call() -> None:
    events = _FakeEventService()
    token = _with_event_service(events)
    try:
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "search", "id": "call-1", "args": {"q": "hello"}},
                {"name": "fetch", "id": "call-2", "args": {"url": "https://x"}},
            ],
        )
        _StubAgent()._notify_tool_usage(ai_msg)

        tool_events = [e for e in events.published if isinstance(e, AgentToolCalled)]
        assert {e.tool_name for e in tool_events} == {"search", "fetch"}
        assert {e.tool_call_id for e in tool_events} == {"call-1", "call-2"}
        # tool_args is JSON-encoded so it round-trips through the SQLite log
        import json
        args_by_tool = {e.tool_name: json.loads(e.tool_args) for e in tool_events}
        assert args_by_tool == {"search": {"q": "hello"}, "fetch": {"url": "https://x"}}
    finally:
        _event_service_override.reset(token)


def test_notify_tool_response_emits_agent_tool_responded() -> None:
    events = _FakeEventService()
    token = _with_event_service(events)
    try:
        msg = ToolMessage(content="result body", name="search", tool_call_id="call-1")
        _StubAgent()._notify_tool_response(msg)

        evt = events.published[0]
        assert isinstance(evt, AgentToolResponded)
        assert evt.tool_name == "search"
        assert evt.tool_call_id == "call-1"
        assert evt.content == "result body"
        assert evt.content_length == len("result body")
    finally:
        _event_service_override.reset(token)


def test_notify_ai_message_emits_agent_ai_message_emitted() -> None:
    events = _FakeEventService()
    token = _with_event_service(events)
    try:
        _StubAgent()._notify_ai_message(AIMessage(content="hello world"), "tester")
        evt = events.published[0]
        assert isinstance(evt, AgentAIMessageEmitted)
        assert evt.agent_name == "tester"
        assert evt.content == "hello world"
        assert evt.content_length == len("hello world")
    finally:
        _event_service_override.reset(token)


def test_notify_agent_routing_emits_agent_routed_with_target() -> None:
    events = _FakeEventService()
    token = _with_event_service(events)
    try:
        _StubAgent(name="supervisor")._notify_agent_routing("specialist")
        evt = events.published[0]
        assert isinstance(evt, AgentRouted)
        assert evt.agent_name == "supervisor"
        assert evt.routed_to == "specialist"
    finally:
        _event_service_override.reset(token)


def test_user_message_event_class_constructs_with_content() -> None:
    """AgentUserMessageReceived round-trips prompt text + identity."""
    evt = AgentUserMessageReceived(
        agent_name="tester",
        content="hi there",
        content_length=len("hi there"),
        user_id="u",
        chat_id="c",
        workspace_id="w",
    )
    assert evt.content == "hi there"
    assert evt.content_length == 8


def test_agent_invocation_completed_event_class_constructs() -> None:
    """Sanity: the AgentInvocationCompleted class accepts the fields we publish."""
    evt = AgentInvocationCompleted(
        agent_name="tester",
        content_length=42,
        user_id="u",
        chat_id="c",
        workspace_id="w",
    )
    assert evt.content_length == 42
