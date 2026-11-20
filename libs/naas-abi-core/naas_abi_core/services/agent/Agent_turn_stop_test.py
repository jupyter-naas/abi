"""A stopped turn (``agent_turn_stop``) starts no model call and no tool call.

Driven through ``stream_invoke``, the path a chat turn takes: the stop is read in
the invoke thread and in LangGraph's node threads, which the ContextVar reaches
through ``copy_context``.
"""

from __future__ import annotations

import threading
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.services.agent.Agent import (
    TURN_STOPPED_TOOL_REPLY,
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.agent.context import agent_turn_stop

STOP = threading.Event()
RAN: list[str] = []


class _ScriptedChatModel(BaseChatModel):
    script: list[AIMessage]
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

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
def search_files(query: str) -> str:
    """Search the workspace files; the user presses Stop while it runs.

    Args:
        query (str): What to search.
    """
    RAN.append("search_files")
    STOP.set()
    return f"3 files match {query}"


@tool
def delete_files(query: str) -> str:
    """Delete the files a search found.

    Args:
        query (str): What to delete.
    """
    RAN.append("delete_files")
    return f"deleted {query}"


TOOL_CALLS = [
    {
        "name": "search_files",
        "args": {"query": "drafts"},
        "id": "call-1",
        "type": "tool_call",
    },
    {
        "name": "delete_files",
        "args": {"query": "drafts"},
        "id": "call-2",
        "type": "tool_call",
    },
]


def _agent(thread_id: str) -> tuple[Agent, _ScriptedChatModel]:
    model = _ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=TOOL_CALLS),
            AIMessage(content="Done."),
        ]
    )
    agent = Agent(
        name="turn_stop_agent",
        description="Calls two tools, then answers",
        chat_model=model,
        tools=[search_files, delete_files],
        agents=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id=thread_id),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )
    return agent, model


def _run(agent: Agent) -> list[dict[str, Any]]:
    token = agent_turn_stop.set(STOP)
    try:
        return list(agent.stream_invoke("clean up my drafts"))
    finally:
        agent_turn_stop.reset(token)


def _thread_messages(agent: Agent, thread_id: str) -> list[BaseMessage]:
    return agent.graph.get_state({"configurable": {"thread_id": thread_id}}).values[
        "messages"
    ]


def test_a_stop_during_a_tool_call_runs_no_further_tool_and_no_model() -> None:
    STOP.clear()
    RAN.clear()
    agent, model = _agent("stop-mid-tools")

    _run(agent)

    assert RAN == ["search_files"]
    assert model.calls == 1
    # Each tool call the model made is answered, so the thread can take a next turn.
    replies = {
        m.tool_call_id: m.content
        for m in _thread_messages(agent, "stop-mid-tools")
        if isinstance(m, ToolMessage)
    }
    assert replies == {
        "call-1": "3 files match drafts",
        "call-2": TURN_STOPPED_TOOL_REPLY,
    }


def test_a_turn_stopped_before_it_starts_calls_no_model() -> None:
    STOP.set()
    RAN.clear()
    agent, model = _agent("stop-before")

    _run(agent)

    assert model.calls == 0
    assert RAN == []


def test_a_turn_nobody_stops_runs_every_tool() -> None:
    STOP.clear()
    RAN.clear()
    agent, model = _agent("no-stop")

    list(agent.stream_invoke("clean up my drafts"))

    assert RAN == ["search_files", "delete_files"]
    assert model.calls == 2
