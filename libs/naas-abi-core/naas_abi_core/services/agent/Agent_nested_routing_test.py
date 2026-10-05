"""Routing to an active agent below a direct child, across turns.

Each agent's graph holds only its direct children, while the active agent's
name is shared by the whole tree. A follow-up turn must enter the child whose
subtree holds the active agent; an active agent outside the tree must not send
the turn to a node that does not exist.
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
    tool_call,
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


def test_follow_up_reaches_a_grandchild_through_its_parent():
    state = AgentSharedState(thread_id="t", supervisor_agent="lead")
    memory = MemorySaver()
    worker = _agent(
        "worker",
        [AIMessage(content="first"), AIMessage(content="second")],
        state=state,
        memory=memory,
    )
    manager = _agent(
        "manager",
        [tool_call("transfer_to_worker", {}, "h2")],
        agents=[worker],
        state=state,
        memory=memory,
    )
    lead = _agent(
        "lead",
        [tool_call("transfer_to_manager", {}, "h1")],
        agents=[manager],
        state=state,
        memory=memory,
    )
    assert lead.invoke("task") == "first"
    assert lead.invoke("follow-up") == "second"


def test_an_active_agent_outside_the_tree_hands_the_turn_back():
    state = AgentSharedState(thread_id="t", supervisor_agent="lead")
    lead = _agent("lead", [AIMessage(content="lead answers")], state=state)
    state.set_current_active_agent("ghost")
    assert lead.invoke("hello") == "lead answers"
    assert state.current_active_agent == "lead"
