"""A tool may carry its JSON Schema as a dict: tools served by a remote module do.

Regression: ``call_tools`` read the tool's fields from a pydantic input model, so a
tool whose ``args_schema`` is a plain JSON Schema dict failed with ``KeyError:
'properties'`` before it ran.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
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


def _agent(tool: StructuredTool, args: dict[str, Any] | None = None) -> Agent:
    return Agent(
        name="dict_schema_agent",
        description="Calls a tool described by a JSON Schema",
        chat_model=_ScriptedChatModel(
            script=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool.name,
                            "args": args if args is not None else {"city": "Paris"},
                            "id": "c1",
                        }
                    ],
                ),
                AIMessage(content="done"),
            ]
        ),
        tools=[tool],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="dict-schema"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )


def test_a_tool_with_a_dict_schema_runs():
    calls: list[dict[str, Any]] = []

    def forecast(**arguments: Any) -> str:
        calls.append(arguments)
        return "sunny"

    agent = _agent(
        StructuredTool(
            name="get_forecast",
            description="Get the weather forecast for a city.",
            args_schema={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
            func=forecast,
        )
    )
    assert agent.invoke("weather in Paris?") == "done"
    assert calls == [{"city": "Paris"}]


def test_a_dict_schema_without_properties_runs_too():
    calls: list[dict[str, Any]] = []

    def ping(**arguments: Any) -> str:
        calls.append(arguments)
        return "pong"

    agent = _agent(
        StructuredTool(
            name="ping",
            description="Ping.",
            args_schema={"type": "object"},
            func=ping,
        ),
        args={},
    )
    assert agent.invoke("ping") == "done"
    assert calls == [{}]
