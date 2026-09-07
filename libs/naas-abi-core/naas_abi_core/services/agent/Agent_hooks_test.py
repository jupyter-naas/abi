# mypy: disable-error-code="arg-type,misc"
"""Tests for the `onHumanMessage` / `onAImessage` subclass hooks.

These hooks exist so an agent inheriting from `Agent` can observe the
conversation. They are fire-and-forget by contract: the runtime ignores what
they return and never lets a failing hook break the turn.

As in `Agent_events_test.py`, we bind the real methods onto an Agent-shaped
stub — a real `Agent` needs a live chat model plus LangGraph compilation, which
is far more surface than these wiring tests need.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from naas_abi_core.services.agent.Agent import Agent

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _HookAgent:
    """Agent-shaped stub exposing only what the hooks + their call sites need."""

    def __init__(self, name: str = "tester", chunks: list[Any] | None = None) -> None:
        self._name = name
        self._agents: list[Any] = []
        self._event_queue = SimpleNamespace(put=lambda _: None)
        self._on_ai_message = lambda _, __: None
        self._state = SimpleNamespace(thread_id="t-1")
        self.graph = SimpleNamespace(stream=lambda *a, **kw: iter(chunks or []))
        self.human_calls: list[Any] = []
        self.ai_calls: list[tuple[Any, str]] = []

    # Bind the real implementations so we exercise the actual code paths.
    _identity = Agent._identity
    _publish_agent_event = Agent._publish_agent_event
    _stringify_content = Agent._stringify_content
    _has_tool_calls = staticmethod(Agent._has_tool_calls)
    _call_hook = Agent._call_hook
    onHumanMessage = Agent.onHumanMessage
    onAImessage = Agent.onAImessage
    _notify_ai_message = Agent._notify_ai_message
    stream = Agent.stream


class _RecordingAgent(_HookAgent):
    """Subclass that overrides both hooks, the way a user's agent would."""

    def onHumanMessage(self, message: Any) -> None:
        self.human_calls.append(message)

    def onAImessage(self, message: Any, agent_name: str) -> None:
        self.ai_calls.append((message, agent_name))


class _RaisingAgent(_HookAgent):
    """Subclass whose hooks blow up — the runtime must absorb that."""

    def onHumanMessage(self, message: Any) -> None:
        raise RuntimeError("boom in human hook")

    def onAImessage(self, message: Any, agent_name: str) -> None:
        raise RuntimeError("boom in ai hook")


class _ReturningAgent(_HookAgent):
    """Subclass whose hooks return values — the runtime must ignore them."""

    def onHumanMessage(self, message: Any) -> Any:
        return "ignored"

    def onAImessage(self, message: Any, agent_name: str) -> Any:
        return {"also": "ignored"}


# ---------------------------------------------------------------------------
# Base class behaviour
# ---------------------------------------------------------------------------


def test_base_hooks_are_noops_returning_none() -> None:
    agent = _HookAgent()

    assert agent.onHumanMessage(HumanMessage(content="hi")) is None
    assert agent.onAImessage(AIMessage(content="hello"), "tester") is None


# ---------------------------------------------------------------------------
# onAImessage
# ---------------------------------------------------------------------------


def test_notify_ai_message_invokes_on_ai_message_hook() -> None:
    agent = _RecordingAgent()
    message = AIMessage(content="hello world")

    agent._notify_ai_message(message, "tester")

    assert len(agent.ai_calls) == 1
    received, agent_name = agent.ai_calls[0]
    assert received is message
    assert agent_name == "tester"


def test_on_ai_message_hook_receives_originating_sub_agent_name() -> None:
    """Sub-agent output flows through the parent's notifier, so the hook must
    report who actually produced the message, not the parent."""
    agent = _RecordingAgent(name="supervisor")

    agent._notify_ai_message(AIMessage(content="from the specialist"), "specialist")

    assert agent.ai_calls[0][1] == "specialist"


def test_raising_on_ai_message_hook_does_not_break_notification() -> None:
    agent = _RaisingAgent()
    seen: list[Any] = []
    agent._on_ai_message = lambda message, name: seen.append((message, name))

    agent._notify_ai_message(AIMessage(content="hello"), "tester")  # must not raise

    # The registered callback still ran: a broken hook is isolated.
    assert len(seen) == 1


def test_returning_on_ai_message_hook_value_is_ignored() -> None:
    agent = _ReturningAgent()

    assert agent._notify_ai_message(AIMessage(content="hello"), "tester") is None


# ---------------------------------------------------------------------------
# onHumanMessage
# ---------------------------------------------------------------------------


def test_stream_invokes_on_human_message_hook_with_the_human_message() -> None:
    agent = _RecordingAgent()

    list(agent.stream("what is the weather?"))

    assert len(agent.human_calls) == 1
    message = agent.human_calls[0]
    assert isinstance(message, HumanMessage)
    assert message.content == "what is the weather?"


def test_stream_fires_on_human_message_once_per_turn() -> None:
    agent = _RecordingAgent()

    list(agent.stream("first"))
    list(agent.stream("second"))

    assert [m.content for m in agent.human_calls] == ["first", "second"]


def test_raising_hooks_do_not_break_stream() -> None:
    """Both hooks blow up on the same turn; the stream must still complete."""
    chunk = ((), {"call_model": {"messages": [AIMessage(content="hi")]}})
    agent = _RaisingAgent(chunks=[chunk])
    seen: list[Any] = []
    agent._on_ai_message = lambda message, name: seen.append((message, name))

    assert list(agent.stream("hello")) == [chunk]
    # onAImessage also raised, yet the registered callback still ran.
    assert len(seen) == 1


def test_returning_on_human_message_hook_value_is_ignored() -> None:
    agent = _ReturningAgent()

    assert list(agent.stream("hello")) == []


def test_stream_feeds_the_same_human_message_to_the_graph() -> None:
    """The message handed to the hook is the one the graph actually receives."""
    captured: list[Any] = []

    def capturing_stream(payload: Any, **kwargs: Any) -> Any:
        captured.append(payload)
        return iter([])

    agent = _RecordingAgent()
    agent.graph = SimpleNamespace(stream=capturing_stream)

    list(agent.stream("trace me"))

    assert captured[0]["messages"][0] is agent.human_calls[0]
