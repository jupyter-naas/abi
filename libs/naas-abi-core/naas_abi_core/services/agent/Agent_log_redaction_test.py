"""What the agent logs at INFO or above carries no content: no model answer,
no database password."""

from __future__ import annotations

import time
from typing import Annotated

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import InjectedState
from naas_abi_core.services.agent import Agent as agent_module
from naas_abi_core.utils.Logger import logger


@pytest.fixture
def logged():
    lines: list[str] = []
    sink = logger.add(lines.append, level="INFO", format="{message}")
    yield lines
    logger.remove(sink)


def test_call_tools_without_tool_calls_does_not_log_the_answer(logged):
    answer = AIMessage(content="the confidential answer", id="msg-1")

    commands = agent_module.Agent.call_tools(None, {"messages": [answer]})  # type: ignore[arg-type]

    assert commands[0].goto == "__end__"
    text = "".join(logged)
    assert "No tool calls found" in text
    assert "msg-1" in text
    assert "confidential" not in text


@pytest.mark.parametrize(
    "error",
    [
        "could not translate host name: nodename nor servname provided, or not known",
        'invalid dsn: missing "=" after "{url}" in connection info string',
    ],
)
def test_a_failed_postgres_checkpointer_does_not_log_the_password(
    monkeypatch, logged, error
):
    url = "postgresql://abi:s3cret-pw@db.invalid:5432/abi"
    monkeypatch.setenv("POSTGRES_URL", url)
    monkeypatch.setattr(agent_module, "get_default_agent_checkpointer", lambda: None)
    monkeypatch.setattr(agent_module, "_shared_checkpointer", None)
    monkeypatch.setattr(agent_module, "_shared_checkpointer_url", None)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    def refuse(*_args, **_kwargs):
        raise RuntimeError(error.format(url=url))

    import psycopg

    monkeypatch.setattr(psycopg.Connection, "connect", refuse)

    checkpointer = agent_module.create_checkpointer()

    assert isinstance(checkpointer, MemorySaver)
    text = "\n".join(logged)
    assert "s3cret-pw" not in text
    assert "Falling back to in-memory checkpointer" in text


@tool
def count_messages(label: str, state: Annotated[list, InjectedState]) -> str:
    """Count the messages. Its ``state`` is declared as the wrong type, so the
    injected conversation is rejected, and the error would quote it.

    Args:
        label: A label.
    """
    return label


def test_a_failing_tool_with_injected_state_does_not_log_the_conversation(logged):
    """The state handed to an ``InjectedState`` tool is the whole conversation;
    a rejected call's error must not carry it into the log (or the history)."""
    from naas_abi_core.services.agent.Agent import (
        Agent,
        AgentConfiguration,
        AgentSharedState,
    )
    from naas_abi_core.services.agent.tests.scripted_chat_model import (
        ScriptedChatModel,
        tool_call,
    )

    llm = ScriptedChatModel.from_script(
        [
            tool_call("count_messages", {"label": "first"}, "c1"),
            AIMessage(content="recovered"),
        ]
    )
    agent = Agent(
        name="redaction_agent",
        description="Calls a tool that rejects its arguments",
        chat_model=llm,
        tools=[count_messages],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="redaction"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )

    assert agent.invoke("my confidential question") == "recovered"

    text = "".join(logged)
    assert "count_messages failed" in text
    assert "confidential" not in text
    shown_to_the_model = " ".join(
        str(m.content) for m in llm.recorder.tool_messages(-1)
    )
    assert "failed" in shown_to_the_model and "confidential" not in shown_to_the_model
