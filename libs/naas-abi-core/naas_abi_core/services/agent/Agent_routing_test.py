"""Routing restored from a thread only targets agents of the graph that runs it.

Nexus and the OpenAI gateway run each turn on a fresh duplicate of the selected
agent, keyed by the conversation's thread, and every engine agent shares one
checkpointer. The thread therefore carries ``current_active_agent`` and
``supervisor_agent`` from whichever agent ran the previous turn, which is not
always the agent running this one.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from pydantic import Field


class Scripted(BaseChatModel):
    """Replies in order (the last one repeats) and records what it was sent."""

    replies: list[AIMessage]
    received: list[list[str]] = Field(default_factory=list)
    system_prompts: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Scripted:
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.system_prompts.append(
            "\n".join(str(m.content) for m in messages if isinstance(m, SystemMessage))
        )
        self.received.append(
            [str(m.content) for m in messages if not isinstance(m, SystemMessage)]
        )
        reply = self.replies[min(len(self.received), len(self.replies)) - 1]
        return ChatResult(generations=[ChatGeneration(message=reply.model_copy())])


def handoff(target: str) -> AIMessage:
    return AIMessage(
        "", tool_calls=[{"name": f"transfer_to_{target}", "args": {}, "id": "call-1"}]
    )


@pytest.fixture(autouse=True)
def _standalone(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)  # dev mode randomizes thread ids
    monkeypatch.delenv("POSTGRES_URL", raising=False)


@pytest.fixture
def saver() -> InMemorySaver:
    # One saver for every agent, as the engine gives them.
    return InMemorySaver()


def agent(
    name: str,
    model: Scripted,
    saver: InMemorySaver,
    agents: list[Agent] | None = None,
    supervised: bool = False,
) -> Agent:
    return Agent(
        name=name,
        description=f"{name} agent.",
        chat_model=model,
        agents=agents,
        memory=saver,
        # A supervisor names itself in its shared state, as AbiAgent does.
        state=AgentSharedState(supervisor_agent=name if supervised else None),
        configuration=AgentConfiguration(system_prompt=f"You are {name}."),
    )


def turn(template: Agent, prompt: str) -> str:
    # As Nexus runs a request: a duplicate of the cached template on the
    # conversation's thread, carrying the template's supervisor forward.
    scoped = template.duplicate(
        agent_shared_state=AgentSharedState(
            thread_id="conversation",
            supervisor_agent=template.state.supervisor_agent,
        )
    )
    return scoped.invoke(prompt)


def test_an_agent_answers_a_thread_another_agent_left(saver):
    first = Scripted(replies=[AIMessage("noted")])
    second = Scripted(replies=[AIMessage("Bob")])

    turn(agent("First", first, saver), "my name is Bob")
    answer = turn(agent("Second", second, saver), "what is my name?")

    assert answer == "Bob"
    assert second.received == [["my name is Bob", "noted", "what is my name?"]]


def test_an_agent_answers_a_thread_left_on_another_agents_sub_agent(saver):
    lead = Scripted(replies=[handoff("Helper")])
    helper = Scripted(replies=[AIMessage("hi Bob")])
    other = Scripted(replies=[AIMessage("you are Bob")])

    turn(
        agent("Lead", lead, saver, agents=[agent("Helper", helper, saver)]),
        "I am Bob",
    )
    answer = turn(agent("Other", other, saver), "who am I?")

    assert answer == "you are Bob"
    assert len(other.received) == 1


def test_a_supervisor_that_left_the_thread_does_not_supervise_the_next_agent(saver):
    lead = Scripted(replies=[AIMessage("noted")])
    documents = Scripted(replies=[AIMessage("drafted")])

    turn(agent("Lead", lead, saver, supervised=True), "my name is Bob")
    answer = turn(agent("Documents", documents, saver), "draft a letter")

    assert answer == "drafted"
    assert "SUPERVISOR SYSTEM PROMPT" not in documents.system_prompts[0]


def test_a_handoff_still_continues_with_the_sub_agent(saver):
    lead = Scripted(replies=[handoff("Helper")])
    helper = Scripted(replies=[AIMessage("hi Bob"), AIMessage("you are Bob")])

    def tree() -> Agent:
        return agent("Lead", lead, saver, agents=[agent("Helper", helper, saver)])

    turn(tree(), "I am Bob")
    answer = turn(tree(), "who am I?")

    assert answer == "you are Bob"
    assert len(lead.received) == 1  # turn two went straight to the sub-agent


def test_a_nested_handoff_continues_through_the_intermediate_agent(saver):
    lead = Scripted(replies=[handoff("Mid")])
    mid = Scripted(replies=[handoff("Leaf")])
    leaf = Scripted(replies=[AIMessage("leaf one"), AIMessage("leaf two")])

    def tree() -> Agent:
        return agent(
            "Lead",
            lead,
            saver,
            agents=[agent("Mid", mid, saver, agents=[agent("Leaf", leaf, saver)])],
        )

    assert turn(tree(), "hello") == "leaf one"
    assert turn(tree(), "again") == "leaf two"
    assert (len(lead.received), len(mid.received)) == (1, 1)


def test_returning_to_an_agent_after_another_one_starts_with_that_agent(saver):
    lead = Scripted(replies=[handoff("Helper"), AIMessage("lead again")])
    helper = Scripted(replies=[AIMessage("hi Bob")])
    other = Scripted(replies=[AIMessage("other")])

    def tree() -> Agent:
        return agent("Lead", lead, saver, agents=[agent("Helper", helper, saver)])

    turn(tree(), "I am Bob")
    turn(agent("Other", other, saver), "hello")
    answer = turn(tree(), "back to you")

    # Other took the thread over, so Lead's earlier handoff no longer holds.
    assert answer == "lead again"
    assert len(helper.received) == 1
