"""End-to-end tests for the `Agent.stream` loop, driven by a scripted model.

Unlike `Agent_events_test.py` (which binds `_notify_*` onto an Agent-shaped
stub) and `Agent_test.py` (which needs a live OpenAI key), these tests build a
real `Agent`, compile the real LangGraph, and consume the real streaming
surface. The chat model is scripted and the tools are trivial, so the run is
hermetic: no network, no credentials, no server.

They exist because the multi-tool `tool_response` regression could not be
caught by a unit test of the dedupe key alone. Only the full loop shows what
LangGraph actually hands to `Agent.stream` for a turn that calls two tools.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _ScriptedChatModel(BaseChatModel):
    """Replays a fixed list of AI messages, one per `call_model` invocation.

    `bind_tools` returns `self` so the script survives tool binding; the agent
    binds the model twice (with and without workspace-gated tools).
    """

    script: list[AIMessage]
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    @property
    def _identifying_params(self) -> dict:
        return {}

    def bind_tools(self, tools: Any, **kwargs: Any) -> _ScriptedChatModel:
        del tools, kwargs
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del messages, stop, run_manager, kwargs
        index = min(self.calls, len(self.script) - 1)
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=self.script[index])])


@tool
def list_sections(deck: str) -> str:
    """List the sections of a deck.

    Args:
        deck (str): The deck to list.
    """
    return f"sections of {deck}"


@tool
def write_section(section: str) -> str:
    """Write one section of a deck.

    Args:
        section (str): The section to write.
    """
    return f"wrote {section}"


def _two_tool_call_turn(tool_calls: list[dict[str, Any]]) -> list[AIMessage]:
    """A turn that calls tools once, then answers in plain text."""
    return [
        AIMessage(content="", tool_calls=tool_calls),
        AIMessage(content="done"),
    ]


def _tool_response_payloads(tool_calls: list[dict[str, Any]]) -> list[str]:
    """Stream a turn through a real agent and return its tool_response data."""
    agent = Agent(
        name="stream_dedupe_agent",
        description="Drives the stream loop with a scripted model",
        chat_model=_ScriptedChatModel(script=_two_tool_call_turn(tool_calls)),
        tools=[list_sections, write_section],
        agents=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="stream-dedupe"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )

    return [
        event["data"]
        for event in agent.stream_invoke("build the deck")
        if event["event"] == "tool_response"
    ]


# ---------------------------------------------------------------------------
# Regression: one tool_response per tool call in a turn
# ---------------------------------------------------------------------------


def test_two_different_tools_in_a_turn_stream_two_tool_responses() -> None:
    """Regression: deduping on `ToolMessage.id` dropped every response but the
    first, because LangChain leaves that field unset. The Slides preview only
    reloads on `tool_response`, so a deck written by the second tool of a turn
    never refreshed."""
    payloads = _tool_response_payloads(
        [
            {"name": "list_sections", "args": {"deck": "q3"}, "id": "call-1"},
            {"name": "write_section", "args": {"section": "intro"}, "id": "call-2"},
        ]
    )

    assert payloads == ["sections of q3", "wrote intro"]


def test_the_same_tool_called_twice_streams_two_tool_responses() -> None:
    """Same tool, two `tool_call_id`s. The dedupe key must separate the calls,
    not the tool names."""
    payloads = _tool_response_payloads(
        [
            {"name": "write_section", "args": {"section": "intro"}, "id": "call-1"},
            {"name": "write_section", "args": {"section": "outro"}, "id": "call-2"},
        ]
    )

    assert payloads == ["wrote intro", "wrote outro"]
