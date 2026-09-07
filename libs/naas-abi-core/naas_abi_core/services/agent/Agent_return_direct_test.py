"""Turn-level tests for tools declared with `return_direct=True`.

`return_direct` means "hand this tool's output straight back to the user, with
no second model pass". When a model asks for two such tools in one turn, both
outputs are answers, so both have to reach the user.

These tests drive a real `Agent` over the real compiled LangGraph with a
scripted chat model, and read the result off `stream_invoke` -- the same
surface the API streams to the browser. A unit test of `call_tools` in
isolation would not have caught the regression they cover: the collapse to
`results[-1]` only becomes visible once a full turn is streamed out.
"""

from __future__ import annotations

from typing import Any

import pytest
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


@tool(return_direct=True)
def search_the_web(query: str) -> str:
    """Search the web and return the answer verbatim.

    Args:
        query (str): What to look up.
    """
    return f"web says {query}"


@tool(return_direct=True)
def search_the_archive(query: str) -> str:
    """Search the internal archive and return the answer verbatim.

    Args:
        query (str): What to look up.
    """
    return f"archive says {query}"


def _assistant_reply(tool_calls: list[dict[str, Any]]) -> str:
    """Stream one turn through a real agent and return what the user reads.

    Joins the assistant messages the turn emitted with the final answer the
    stream terminates on, so a fix that surfaces content on only one of those
    two paths still fails.
    """
    agent = Agent(
        name="return_direct_agent",
        description="Drives a multi tool turn with a scripted model",
        chat_model=_ScriptedChatModel(
            script=[
                AIMessage(content="", tool_calls=tool_calls),
                AIMessage(content="done"),
            ]
        ),
        tools=[search_the_web, search_the_archive],
        agents=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="return-direct"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )

    ai_messages: list[str] = []
    final: list[str] = []
    for event in agent.stream_invoke("what do the sources say"):
        if event["event"] == "ai_message":
            ai_messages.append(event["data"])
        elif event["event"] == "message":
            final.append(event["data"])

    return "\n".join([*ai_messages, *final])


# ---------------------------------------------------------------------------
# Regression: every return_direct output in a turn reaches the user
# ---------------------------------------------------------------------------


def test_two_return_direct_tools_in_a_turn_surface_both_outputs() -> None:
    """Regression: `call_tools` built the user-facing reply from `results[-1]`,
    so in a turn calling two `return_direct` tools the first tool's output was
    dropped without a warning, an error, or a trace in the reply."""
    reply = _assistant_reply(
        [
            {"name": "search_the_web", "args": {"query": "q3"}, "id": "call-1"},
            {"name": "search_the_archive", "args": {"query": "q3"}, "id": "call-2"},
        ]
    )

    assert "web says q3" in reply
    assert "archive says q3" in reply
    assert reply.index("web says q3") < reply.index("archive says q3")


def test_the_same_return_direct_tool_called_twice_surfaces_both_outputs() -> None:
    """Same tool, two `tool_call_id`s. Both calls answer the user, so both
    answers have to be in the reply."""
    reply = _assistant_reply(
        [
            {"name": "search_the_web", "args": {"query": "revenue"}, "id": "call-1"},
            {"name": "search_the_web", "args": {"query": "headcount"}, "id": "call-2"},
        ]
    )

    assert "web says revenue" in reply
    assert "web says headcount" in reply


_IMAGE = {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}


@pytest.mark.parametrize(
    ("outputs", "expected"),
    [
        (["first", "second"], "first\n\nsecond"),
        ([[_IMAGE]], [_IMAGE]),
        ([[_IMAGE], [_IMAGE]], [_IMAGE, _IMAGE]),
        (["caption", [_IMAGE]], [{"type": "text", "text": "caption"}, _IMAGE]),
        ([[_IMAGE], "caption"], [_IMAGE, {"type": "text", "text": "caption"}]),
        (
            [[{"type": "text", "text": "caption"}, _IMAGE], []],
            [{"type": "text", "text": "caption"}, _IMAGE],
        ),
    ],
)
def test_direct_reply_preserves_content_in_graph(
    outputs: list[Any], expected: Any
) -> None:
    """The checkpoint must retain every block without another model pass."""

    @tool(return_direct=True)
    def produce_content(index: int) -> Any:
        """Return the requested content."""
        return outputs[index]

    model = _ScriptedChatModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "produce_content", "args": {"index": i}, "id": f"call-{i}"}
                    for i in range(len(outputs))
                ],
            )
        ]
    )
    agent = Agent(
        name="content_agent",
        description="Test structured direct replies",
        chat_model=model,
        tools=[produce_content],
        agents=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="content-test"),
        enable_default_tools=False,
    )
    list(agent.stream("Return the content"))
    state = agent.graph.get_state({"configurable": {"thread_id": "content-test"}})
    reply = state.values["messages"][-1]
    assert isinstance(reply, AIMessage)
    assert reply.content == expected
    assert model.calls == 1
