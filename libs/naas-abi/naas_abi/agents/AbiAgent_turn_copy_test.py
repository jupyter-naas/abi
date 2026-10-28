"""Abi's prompt names the sub-agents a turn's copy has, never one its caller may
not use, and the cached template's prompt never changes for a turn."""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.agent.Agent_keep_subagents_test import (
    _Model,
    _Words,
    lookup,
)

MESSAGES = [HumanMessage(content="hello")]


def _child(name: str) -> Agent:
    return Agent(
        name=name,
        description=f"The {name} agent.",
        chat_model=_Model(),
        tools=[],
        agents=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="t"),
        configuration=AgentConfiguration(system_prompt=f"You are {name}."),
        enable_default_tools=False,
    )


def _abi() -> AbiAgent:
    """Abi as ``AbiAgent.New`` builds it, with two sub-agents and no engine."""
    agents = [_child("Alpha"), _child("Beta")]
    prompt = AbiAgent.system_prompt.replace(
        "[TOOLS]", "- lookup: Look something up."
    ).replace("[AGENTS]", AbiAgent.agents_section(agents))
    return AbiAgent(
        name="Abi",
        description="The supervisor.",
        chat_model=_Model(),
        embedding_model=_Words(),
        tools=[lookup],
        agents=agents,
        intents=AbiAgent.get_intents(agents=agents),
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="t"),
        configuration=AgentConfiguration(system_prompt=prompt),
    )


def _prompt(agent: Agent) -> str:
    return agent._configuration.get_system_prompt(MESSAGES)


def test_a_turn_copy_names_only_the_agents_it_keeps():
    abi = _abi()
    before = _prompt(abi)
    assert "- Alpha: The Alpha agent." in before and "- Beta: The Beta agent." in before

    copy = abi.duplicate(keep=lambda agent: agent.name != "Beta")
    assert "- Alpha: The Alpha agent." in _prompt(copy)
    assert "Beta" not in _prompt(copy)
    assert copy._configuration is not abi._configuration
    # The template, which every other turn copies, is untouched.
    assert _prompt(abi) == before
    # A copy with every sub-agent shares the template's configuration.
    assert abi.duplicate()._configuration is abi._configuration


def test_the_prune_backstop_rewrites_the_copy_never_the_template(monkeypatch):
    """A copy made without ``keep`` (under a parent whose ``duplicate`` takes
    none) is pruned after the fact: its own prompt changes, not the template's."""
    from naas_abi.apps.nexus.apps.api.app.services import provider_runtime as runtime

    abi = _abi()
    before = _prompt(abi)
    copy = abi.duplicate()
    alpha = next(a for a in copy._agents if a.name == "Alpha")
    own_class = runtime._inprocess_agent_class_name
    monkeypatch.setattr(
        runtime,
        "_inprocess_agent_class_name",
        lambda agent: "only/Alpha" if agent is alpha else own_class(agent),
    )

    runtime._prune_inprocess_subagents_for_roster(copy, frozenset({"only/Alpha"}))

    assert [a.name for a in copy._agents] == ["Alpha"]
    assert "Beta" not in _prompt(copy)
    assert _prompt(abi) == before
