"""Caller-provided thread ids must survive Agent construction."""

from naas_abi_core.services.agent.Agent import (
    AgentSharedState,
    _maybe_randomize_dev_thread_id,
)


def test_dev_env_does_not_overwrite_conversation_id(monkeypatch) -> None:
    monkeypatch.setenv("ENV", "dev")
    state = AgentSharedState(thread_id="conv-7gbvzx7qzj")

    _maybe_randomize_dev_thread_id(state)

    assert state.thread_id == "conv-7gbvzx7qzj"


def test_dev_env_isolates_default_cli_thread(monkeypatch) -> None:
    monkeypatch.setenv("ENV", "dev")
    state = AgentSharedState(thread_id="1")

    _maybe_randomize_dev_thread_id(state)

    assert state.thread_id != "1"


def test_non_dev_env_keeps_default_thread(monkeypatch) -> None:
    monkeypatch.delenv("ENV", raising=False)
    state = AgentSharedState(thread_id="1")

    _maybe_randomize_dev_thread_id(state)

    assert state.thread_id == "1"


def test_agent_construct_keeps_conversation_id_when_env_dev(monkeypatch) -> None:
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from naas_abi_core.services.agent.Agent import Agent

    monkeypatch.setenv("ENV", "dev")
    agent = Agent(
        name="Thread Id Agent",
        description="Keeps conversation ids",
        chat_model=FakeListChatModel(responses=["ok"]),
        state=AgentSharedState(thread_id="conv-7gbvzx7qzj"),
        enable_default_tools=False,
    )

    assert agent.state.thread_id == "conv-7gbvzx7qzj"


def test_agent_duplicate_keeps_conversation_id_when_env_dev(monkeypatch) -> None:
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from naas_abi_core.services.agent.Agent import Agent

    monkeypatch.setenv("ENV", "dev")
    agent = Agent(
        name="Thread Id Agent",
        description="Keeps conversation ids",
        chat_model=FakeListChatModel(responses=["ok"]),
        enable_default_tools=False,
    )
    dup = agent.duplicate(
        agent_shared_state=AgentSharedState(thread_id="conv-7gbvzx7qzj")
    )

    assert dup.state.thread_id == "conv-7gbvzx7qzj"
