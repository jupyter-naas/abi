"""Routing edge cases the persisted-thread cases of Agent_routing_test.py miss.

An active agent set on the shared state (not read back from a thread) that is
outside the tree must not send the turn to a node that does not exist.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.agent.tests.scripted_chat_model import (
    ScriptedChatModel,
)


def _agent(name, script, agents=(), state=None, memory=None):
    return Agent(
        name=name,
        description=f"The {name}",
        chat_model=ScriptedChatModel.from_script(script),
        agents=list(agents),
        memory=memory or MemorySaver(),
        state=state or AgentSharedState(thread_id="t", supervisor_agent="lead"),
        configuration=AgentConfiguration(system_prompt=f"You are the {name}."),
    )


def test_an_active_agent_outside_the_tree_hands_the_turn_back():
    state = AgentSharedState(thread_id="t", supervisor_agent="lead")
    lead = _agent("lead", [AIMessage(content="lead answers")], state=state)
    state.set_current_active_agent("ghost")
    assert lead.invoke("hello") == "lead answers"
    assert state.current_active_agent == "lead"
