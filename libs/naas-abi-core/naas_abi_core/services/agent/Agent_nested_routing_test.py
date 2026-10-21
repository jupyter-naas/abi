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


def test_an_active_agent_outside_the_tree_hands_the_turn_back():
    state = AgentSharedState(thread_id="t", supervisor_agent="lead")
    lead = _agent("lead", [AIMessage(content="lead answers")], state=state)
    state.set_current_active_agent("ghost")
    assert lead.invoke("hello") == "lead answers"
    assert state.current_active_agent == "lead"


def _three_levels(worker_script, manager_script=None, lead_script=None):
    """lead -> manager -> worker, every node sharing ``supervisor_agent="lead"``."""
    state = AgentSharedState(thread_id="t", supervisor_agent="lead")
    memory = MemorySaver()
    worker = _agent("worker", worker_script, state=state, memory=memory)
    manager = _agent(
        "manager",
        manager_script
        or [tool_call("transfer_to_worker", {}, "h2"), AIMessage(content="manager")],
        agents=[worker],
        state=state,
        memory=memory,
    )
    lead = _agent(
        "lead",
        lead_script
        or [tool_call("transfer_to_manager", {}, "h1"), AIMessage(content="lead")],
        agents=[manager],
        state=state,
        memory=memory,
    )
    return lead, state


def test_a_help_request_from_a_grandchild_reaches_the_top_supervisor():
    """The agent in between must not take the turn: the configured supervisor
    is the one asked, whatever its depth above the requester."""
    lead, state = _three_levels(
        [tool_call("request_help", {"reason": "stuck"}, "h3")],
        lead_script=[
            tool_call("transfer_to_manager", {}, "h1"),
            AIMessage(content="lead helps"),
        ],
    )

    assert lead.invoke("do the task") == "lead helps"
    assert state.current_active_agent == "lead"


def test_a_help_request_from_a_child_still_reaches_its_supervisor():
    state = AgentSharedState(thread_id="t", supervisor_agent="lead")
    memory = MemorySaver()
    worker = _agent(
        "worker",
        [tool_call("request_help", {"reason": "stuck"}, "h2")],
        state=state,
        memory=memory,
    )
    lead = _agent(
        "lead",
        [tool_call("transfer_to_worker", {}, "h1"), AIMessage(content="lead helps")],
        agents=[worker],
        state=state,
        memory=memory,
    )

    assert lead.invoke("do the task") == "lead helps"
