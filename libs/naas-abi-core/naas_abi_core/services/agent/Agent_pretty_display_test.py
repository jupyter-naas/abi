"""Regression: the Markdown pretty-display pass must never blank an answer.

IntentAgent enables the pass by default. It re-invoked the model with tools
bound; when that formatting call came back empty (seen live with qwen via
litellm) or as a tool call, the user's real answer was replaced by "" and the
chat pane showed nothing.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class _ScriptedChatModel(BaseChatModel):
    """Replays one AI message per call; records whether tools were bound."""

    script: list[AIMessage]
    calls: int = 0
    bound_calls: int = 0
    bound: bool = False

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> _ScriptedChatModel:
        del tools, kwargs
        return self.model_copy(update={"bound": True})

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del messages, stop, run_manager, kwargs
        _Counter.calls.append(self.bound)
        index = min(len(_Counter.calls) - 1, len(self.script) - 1)
        return ChatResult(generations=[ChatGeneration(message=self.script[index])])


class _Counter:
    calls: list[bool] = []


def _reply(formatting_output: AIMessage) -> str:
    _Counter.calls = []
    agent = Agent(
        name="pretty_agent",
        description="Answers, then runs the Markdown pass",
        chat_model=_ScriptedChatModel(
            script=[
                AIMessage(content="Apps are discovered from manifest.json."),
                formatting_output,
            ]
        ),
        tools=[],
        agents=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="pretty"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
        markdown_pretty_display=True,
    )
    parts = [
        str(event["data"])
        for event in agent.stream_invoke("how are apps discovered?")
        if event["event"] == "ai_message"
    ]
    return "\n".join(parts)


def test_empty_formatting_output_keeps_the_answer() -> None:
    assert "manifest.json" in _reply(AIMessage(content=""))


def test_tool_call_formatting_output_keeps_the_answer() -> None:
    reply = _reply(
        AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "c1"}])
    )
    assert "manifest.json" in reply


def test_formatted_output_replaces_the_answer() -> None:
    assert _reply(AIMessage(content="**Apps** come from `manifest.json`.")) == (
        "**Apps** come from `manifest.json`."
    )


def test_the_formatting_pass_runs_without_tools_bound() -> None:
    _reply(AIMessage(content="formatted"))
    assert _Counter.calls[-1] is False


# ---------------------------------------------------------------------------
# An agent's own recursion_limit is honored outside Slides turns
# ---------------------------------------------------------------------------


def _looping_agent(cls: type[Agent]) -> Agent:
    from langchain_core.tools import tool

    @tool
    def ping(n: int) -> str:
        """Ping.

        Args:
            n (int): Counter.
        """
        return f"pong {n}"

    calls = [
        AIMessage(
            content="", tool_calls=[{"name": "ping", "args": {"n": i}, "id": f"c{i}"}]
        )
        for i in range(14)
    ]
    return cls(
        name="looping_agent",
        description="Calls a tool 14 times, then answers",
        chat_model=_ScriptedChatModel(script=[*calls, AIMessage(content="finished")]),
        tools=[ping],
        agents=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="loop"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )


def _final(agent: Agent) -> str:
    _Counter.calls = []
    events = list(agent.stream_invoke("go"))
    return "\n".join(
        str(e["data"]) for e in events if e["event"] in {"ai_message", "message"}
    )


def test_default_budget_stops_a_long_turn() -> None:
    assert "step limit" in _final(_looping_agent(Agent))


def test_agent_declared_budget_lets_a_long_turn_finish() -> None:
    class _PatientAgent(Agent):
        recursion_limit = 60

    assert "finished" in _final(_looping_agent(_PatientAgent))


def test_duplicate_keeps_the_declared_budget() -> None:
    class _PatientAgent(Agent):
        recursion_limit = 60

    copy = _looping_agent(_PatientAgent).duplicate()
    assert copy.recursion_limit == 60
    assert "finished" in _final(copy)
