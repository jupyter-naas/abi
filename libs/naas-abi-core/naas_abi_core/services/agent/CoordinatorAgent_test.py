"""Unit tests for CoordinatorAgent's handoff-sanitation logic.

These tests focus on the deterministic pieces of CoordinatorAgent that do NOT
require a live LLM call:
- `_is_routing_announcement` pattern detection
- `_scrub_prior_routing_messages` message rewriting
- `_messages_diff_for_scrub` minimal-diff selection
- `_route_to_subagent` Command structure
- `call_tools` unknown-tool rewriting and silent-handoff sanitization

LLM-dependent paths (`agent_recommender`, `filter_out_intents`, `entity_check`)
have integration coverage via the IntentAgent test suite — adding redundant
network-backed tests here would just slow CI.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from naas_abi_core.services.agent.CoordinatorAgent import (
    CoordinatorAgent,
    _is_routing_announcement,
)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _stub_coordinator(agent_names: list[str]) -> CoordinatorAgent:
    """Build a CoordinatorAgent shell with mocked dependencies.

    We sidestep `__init__` entirely because the real constructor builds a full
    LangGraph + IntentMapper + embeddings index. None of that is needed for the
    pure-Python helpers under test.
    """
    coord: CoordinatorAgent = CoordinatorAgent.__new__(CoordinatorAgent)
    coord._name = "Coordinator"
    fake_agents: list[Any] = []
    for name in agent_names:
        fake = MagicMock()
        fake.name = name
        fake._name = name
        fake._tools_by_name = {}
        fake_agents.append(fake)
    coord._agents = fake_agents
    coord._tools_by_name = {}
    return coord


# --------------------------------------------------------------------------- #
# _is_routing_announcement                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I will transfer your request to the Support Agent", True),
        ("Je vais transférer votre demande", True),
        ("I'm routing your message to the right agent", True),
        ("the task has been transferred to me", True),
        ("the request was routed to me", True),
        ("Hello, how can I help?", False),
        ("I created the Notion page successfully", False),
        ("Let me check what tools I have", False),
        ("", False),
    ],
)
def test_routing_announcement_detection(text: str, expected: bool) -> None:
    assert _is_routing_announcement(text) is expected


# --------------------------------------------------------------------------- #
# _scrub_prior_routing_messages                                               #
# --------------------------------------------------------------------------- #


def test_scrub_blanks_coordinator_owned_messages() -> None:
    coord = _stub_coordinator(["SupportAgent"])
    msgs = [
        HumanMessage(content="Help with my issue", id="h1"),
        AIMessage(
            content="I couldn't route automatically. 1. **SupportAgent**\n",
            id="a1",
            additional_kwargs={"owner": "Coordinator", "coordinator_refusal": True},
        ),
        HumanMessage(content="1", id="h2"),
    ]
    scrubbed = coord._scrub_prior_routing_messages(msgs)
    assert scrubbed[0] is msgs[0]
    assert scrubbed[2] is msgs[2]
    # The coordinator-owned AIMessage is blanked but keeps its id and
    # additional_kwargs so add_messages can update it in place.
    assert scrubbed[1].content == ""
    assert scrubbed[1].id == "a1"
    assert scrubbed[1].additional_kwargs.get("owner") == "Coordinator"


def test_scrub_blanks_routing_announcement_phrases() -> None:
    coord = _stub_coordinator(["SupportAgent"])
    msgs = [
        AIMessage(content="I will transfer your request now.", id="a1"),
        AIMessage(content="Got it, I'll look into that.", id="a2"),
    ]
    scrubbed = coord._scrub_prior_routing_messages(msgs)
    assert scrubbed[0].content == ""
    # Non-routing prose is preserved verbatim.
    assert scrubbed[1] is msgs[1]


def test_scrub_blanks_when_subagent_name_appears_verbatim() -> None:
    coord = _stub_coordinator(["SupportAgent", "Web_Search_Agent"])
    msgs = [
        # Underscore name expands to a space variant — this match should fire.
        AIMessage(
            content="Would you like the Web Search Agent to look at this?", id="a1"
        ),
        # PascalCase name with no underscore: only the exact spelling matches.
        AIMessage(content="Routing this via SupportAgent next.", id="a2"),
        # Innocent content stays put.
        AIMessage(content="What is the weather like?", id="a3"),
    ]
    scrubbed = coord._scrub_prior_routing_messages(msgs)
    assert scrubbed[0].content == ""
    assert scrubbed[1].content == ""
    assert scrubbed[2] is msgs[2]


def test_scrub_preserves_tool_calls_and_kwargs() -> None:
    coord = _stub_coordinator(["SupportAgent"])
    tool_calls = [
        {"id": "tc1", "name": "transfer_to_SupportAgent", "args": {}, "type": "tool_call"}
    ]
    msgs = [
        AIMessage(
            content="I will transfer this to Support",
            id="a1",
            tool_calls=tool_calls,
            additional_kwargs={"foo": "bar"},
        ),
    ]
    scrubbed = coord._scrub_prior_routing_messages(msgs)
    assert scrubbed[0].content == ""
    assert scrubbed[0].id == "a1"
    assert scrubbed[0].tool_calls == tool_calls
    assert scrubbed[0].additional_kwargs.get("foo") == "bar"


# --------------------------------------------------------------------------- #
# _messages_diff_for_scrub                                                    #
# --------------------------------------------------------------------------- #


def test_diff_returns_only_changed_messages() -> None:
    coord = _stub_coordinator(["SupportAgent"])
    original = [
        HumanMessage(content="hi", id="h1"),
        AIMessage(content="I will transfer this", id="a1"),
        AIMessage(content="kept", id="a2"),
    ]
    scrubbed = coord._scrub_prior_routing_messages(original)
    diff = coord._messages_diff_for_scrub(original, scrubbed)
    assert len(diff) == 1
    assert diff[0].id == "a1"
    assert diff[0].content == ""


def test_diff_empty_when_nothing_changed() -> None:
    coord = _stub_coordinator(["SupportAgent"])
    original = [
        HumanMessage(content="hi", id="h1"),
        AIMessage(content="all good here", id="a1"),
    ]
    scrubbed = coord._scrub_prior_routing_messages(original)
    diff = coord._messages_diff_for_scrub(original, scrubbed)
    assert diff == []


# --------------------------------------------------------------------------- #
# _route_to_subagent                                                          #
# --------------------------------------------------------------------------- #


def test_route_to_subagent_sets_state_and_returns_command() -> None:
    coord = _stub_coordinator(["SupportAgent"])
    coord._state = MagicMock()
    coord._notify_agent_routing = MagicMock()

    state = {
        "messages": [
            HumanMessage(content="help me", id="h1"),
            AIMessage(content="I will transfer this", id="a1"),
        ]
    }
    cmd = coord._route_to_subagent("SupportAgent", state)

    coord._state.set_current_active_agent.assert_called_once_with("SupportAgent")
    coord._notify_agent_routing.assert_called_once_with("SupportAgent")
    assert cmd.goto == "SupportAgent"
    # The diffed message list contains exactly the scrubbed AIMessage.
    assert "messages" in cmd.update
    assert len(cmd.update["messages"]) == 1
    assert cmd.update["messages"][0].id == "a1"
    assert cmd.update["messages"][0].content == ""


def test_route_to_subagent_merges_extra_update_intent_mapping() -> None:
    coord = _stub_coordinator(["SupportAgent"])
    coord._state = MagicMock()
    coord._notify_agent_routing = MagicMock()

    state = {"messages": []}
    cmd = coord._route_to_subagent(
        "SupportAgent",
        state,
        extra_update={"intent_mapping": {"intents": []}},
    )

    assert cmd.update == {"intent_mapping": {"intents": []}}


def test_route_to_call_model_sentinel_does_not_set_active_agent() -> None:
    coord = _stub_coordinator(["SupportAgent"])
    coord._state = MagicMock()
    coord._notify_agent_routing = MagicMock()

    cmd = coord._route_to_subagent("call_model", {"messages": []})

    coord._state.set_current_active_agent.assert_not_called()
    coord._notify_agent_routing.assert_not_called()
    assert cmd.goto == "call_model"


# --------------------------------------------------------------------------- #
# call_tools: unknown-tool rewrite + silent handoff                           #
# --------------------------------------------------------------------------- #


def test_call_tools_passes_through_when_no_tool_calls(monkeypatch: Any) -> None:
    """If the last message has no tool calls, defer to the base implementation."""
    coord = _stub_coordinator([])
    state = {"messages": [HumanMessage(content="hi", id="h1")]}

    from naas_abi_core.services.agent import CoordinatorAgent as mod

    captured: dict[str, Any] = {}

    def fake_base(self, s):  # noqa: ANN001
        captured["state"] = s
        return [MagicMock(goto="__end__")]

    monkeypatch.setattr(mod.Agent, "call_tools", fake_base)
    result = coord.call_tools(state)  # type: ignore[arg-type]
    assert captured["state"] is state
    assert result[0].goto == "__end__"


def test_call_tools_rewrites_unknown_tool_to_transfer(monkeypatch: Any) -> None:
    """When the LLM calls a subagent-owned tool by name, rewrite to transfer."""
    coord = _stub_coordinator(["SupportAgent"])
    # The subagent owns `github_create_issue`; the coordinator owns the
    # corresponding handoff tool.
    coord._agents[0]._tools_by_name = {"github_create_issue": MagicMock()}
    coord._tools_by_name = {"transfer_to_SupportAgent": MagicMock()}

    tool_call = {
        "id": "tc1",
        "name": "github_create_issue",
        "args": {"title": "bug"},
        "type": "tool_call",
    }
    state = {
        "messages": [
            HumanMessage(content="open a bug", id="h1"),
            AIMessage(
                content="I'll create the issue", id="a1", tool_calls=[tool_call]
            ),
        ]
    }

    from naas_abi_core.services.agent import CoordinatorAgent as mod

    captured: dict[str, Any] = {}

    def fake_base(self, s):  # noqa: ANN001
        captured["state"] = s
        return [MagicMock(goto="SupportAgent")]

    monkeypatch.setattr(mod.Agent, "call_tools", fake_base)
    coord.call_tools(state)  # type: ignore[arg-type]

    rewritten_msg = captured["state"]["messages"][-1]
    assert isinstance(rewritten_msg, AIMessage)
    # Content stripped, id preserved, tool_call rewritten.
    assert rewritten_msg.content == ""
    assert rewritten_msg.id == "a1"
    assert len(rewritten_msg.tool_calls) == 1
    assert rewritten_msg.tool_calls[0]["name"] == "transfer_to_SupportAgent"
    assert rewritten_msg.tool_calls[0]["id"] == "tc1"


def test_call_tools_strips_handoff_text_on_native_transfer(monkeypatch: Any) -> None:
    """When the LLM emits transfer_to_X with prose, strip the prose."""
    coord = _stub_coordinator(["SupportAgent"])
    coord._tools_by_name = {"transfer_to_SupportAgent": MagicMock()}

    transfer_call = {
        "id": "tc1",
        "name": "transfer_to_SupportAgent",
        "args": {},
        "type": "tool_call",
    }
    state = {
        "messages": [
            HumanMessage(content="help me", id="h1"),
            AIMessage(
                content="I'll transfer you to Support now.",
                id="a1",
                tool_calls=[transfer_call],
            ),
        ]
    }

    from naas_abi_core.services.agent import CoordinatorAgent as mod

    captured: dict[str, Any] = {}

    def fake_base(self, s):  # noqa: ANN001
        captured["state"] = s
        return [MagicMock(goto="SupportAgent")]

    monkeypatch.setattr(mod.Agent, "call_tools", fake_base)
    coord.call_tools(state)  # type: ignore[arg-type]

    last = captured["state"]["messages"][-1]
    assert last.content == ""
    assert last.id == "a1"
    assert last.tool_calls[0]["name"] == "transfer_to_SupportAgent"


def test_call_tools_unknown_tool_returns_graceful_error() -> None:
    """If the tool exists nowhere, emit a ToolMessage end-state instead of crashing."""
    coord = _stub_coordinator(["SupportAgent"])
    tool_call = {
        "id": "tc1",
        "name": "totally_unknown_tool",
        "args": {},
        "type": "tool_call",
    }
    state = {
        "messages": [
            HumanMessage(content="do something", id="h1"),
            AIMessage(content="ok", id="a1", tool_calls=[tool_call]),
        ]
    }
    results = coord.call_tools(state)  # type: ignore[arg-type]
    assert len(results) == 1
    cmd = results[0]
    assert cmd.goto == "__end__"
    tool_msg = cmd.update["messages"][0]
    assert isinstance(tool_msg, ToolMessage)
    assert "not available" in tool_msg.content
    assert tool_msg.tool_call_id == "tc1"
