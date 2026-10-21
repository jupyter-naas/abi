"""What the agent logs at INFO or above carries no content: no model answer,
no database password."""

from __future__ import annotations

import time

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
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
