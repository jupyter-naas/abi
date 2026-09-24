"""Tools that declare ``InjectedState`` receive the graph state when called.

Regression: ``call_tools`` put ``state`` next to the tool call instead of
inside its arguments, so LangChain never saw it and every such tool failed
argument validation ("state: Field required") before running.
"""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import InjectedState
from naas_abi_core.services.agent.Agent import (
    ABIAgentState,
    Agent,
    AgentConfiguration,
    AgentSharedState,
    merge_enabled_capabilities,
)


class _ScriptedChatModel(BaseChatModel):
    script: list[AIMessage]
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> _ScriptedChatModel:
        return self

    def _generate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any
    ) -> ChatResult:
        index = min(self.calls, len(self.script) - 1)
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=self.script[index])])


seen_states: list[dict] = []


@tool
def count_messages(label: str, state: Annotated[dict, InjectedState]) -> str:
    """Count the messages of the conversation.

    Args:
        label: A label echoed back.
    """
    seen_states.append(state)
    return f"{label}: {len(state['messages'])} messages"


def test_injected_state_reaches_the_tool():
    seen_states.clear()
    agent = Agent(
        name="injected_state_agent",
        description="Calls a tool that reads the graph state",
        chat_model=_ScriptedChatModel(
            script=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "count_messages", "args": {"label": "n"}, "id": "c1"}
                    ],
                ),
                AIMessage(content="done"),
            ]
        ),
        tools=[count_messages],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="injected-state"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )

    assert agent.invoke("how long is this conversation") == "done"
    assert len(seen_states) == 1
    assert "messages" in seen_states[0]


issue_filters: list[str] = []


@tool
def list_issues(state: str) -> str:
    """List issues in a given state.

    Args:
        state: open, closed or all.
    """
    issue_filters.append(state)
    return f"{state} issues"


def test_a_plain_state_argument_keeps_the_model_value():
    """Only injected state is replaced: an ordinary ``state`` parameter (like
    ``github_list_issues``'s issue filter) must keep what the model sent."""
    issue_filters.clear()
    agent = Agent(
        name="plain_state_agent",
        description="Calls a tool whose own argument is named state",
        chat_model=_ScriptedChatModel(
            script=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "list_issues", "args": {"state": "closed"}, "id": "c1"}
                    ],
                ),
                AIMessage(content="done"),
            ]
        ),
        tools=[list_issues],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="plain-state"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )

    assert agent.invoke("which issues are closed") == "done"
    assert issue_filters == ["closed"]


class TestMergeEnabledCapabilities:
    def test_enable_appends_without_duplicates(self):
        merged = merge_enabled_capabilities(
            {"a": ["x"]}, {"a": {"enable": ["y", "x", "y"]}}
        )
        assert merged == {"a": ["x", "y"]}

    def test_disable_removes(self):
        merged = merge_enabled_capabilities(
            {"a": ["x", "y"]}, {"a": {"disable": ["x", "unknown"]}}
        )
        assert merged == {"a": ["y"]}

    def test_agents_are_kept_apart(self):
        merged = merge_enabled_capabilities(
            {"a": ["x"], "b": ["z"]}, {"a": {"enable": ["y"]}}
        )
        assert merged == {"a": ["x", "y"], "b": ["z"]}

    def test_a_full_list_replaces_the_agent_entry(self):
        # Sub-graphs hand their final state back to the parent as full values.
        assert merge_enabled_capabilities({"a": ["x"]}, {"a": ["y"]}) == {"a": ["y"]}

    def test_concurrent_operations_in_one_step_all_apply(self):
        once = merge_enabled_capabilities({}, {"a": {"enable": ["x"]}})
        twice = merge_enabled_capabilities(once, {"a": {"enable": ["y"]}})
        assert twice == {"a": ["x", "y"]}

    def test_handles_missing_values(self):
        assert merge_enabled_capabilities(None, None) == {}
        assert merge_enabled_capabilities(None, {"a": {"enable": ["x"]}}) == {
            "a": ["x"]
        }

    def test_state_schema_declares_the_channel(self):
        assert "enabled_capabilities" in ABIAgentState.__annotations__
