"""Engine agents keep today's memory semantics with the document checkpointer.

Until now an engine gave every agent built with ``memory=None`` one shared
PostgresSaver: a thread is keyed by its id alone, whichever agent writes it.
Each scenario runs against that shared saver (an InMemorySaver standing in for
the PostgreSQL tables) and against the engine's document saver, rebuilt from
storage between turns like a restarted process, and both transcripts must match.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from naas_abi_core.engine.context import with_agent_checkpointer_override
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.agent.DocumentCheckpointSaver import (
    DocumentCheckpointSaver,
)
from naas_abi_core.services.agent.IntentAgent import IntentAgent
from naas_abi_core.services.document.DocumentFactory import DocumentFactory
from naas_abi_core.services.document.DocumentService import DocumentService
from pydantic import Field


class Scripted(BaseChatModel):
    """Replies in order (the last one repeats) and records what it was sent."""

    replies: list[AIMessage]
    received: list[list[str]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Scripted:
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(
            [str(m.content) for m in messages if not isinstance(m, SystemMessage)]
        )
        reply = self.replies[min(len(self.received), len(self.replies)) - 1]
        return ChatResult(generations=[ChatGeneration(message=reply.model_copy())])


def handoff(target: str) -> AIMessage:
    return AIMessage(
        "", tool_calls=[{"name": f"transfer_to_{target}", "args": {}, "id": "call-1"}]
    )


class SharedSaver:
    """Today: one process-wide saver that outlives agent rebuilds and restarts."""

    def __init__(self, tmp_path) -> None:
        self.saver = InMemorySaver()

    def restart(self) -> None:
        pass

    def close(self) -> None:
        pass


class EngineDocuments:
    """Now: the engine's document saver, reopened from storage on each restart."""

    def __init__(self, tmp_path) -> None:
        self.path = str(tmp_path / "documents.sqlite")
        self.root: DocumentService | None = None
        self.restart()

    def restart(self) -> None:
        self.close()
        self.root = DocumentService._for_engine(
            DocumentFactory.DocumentAdapterSQLite(self.path)
        )
        self.saver = DocumentCheckpointSaver.for_engine(self.root)

    def close(self) -> None:
        if self.root is not None:
            self.root.adapter.close()


@pytest.fixture(autouse=True)
def _standalone(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)  # dev mode randomizes thread ids
    monkeypatch.delenv("POSTGRES_URL", raising=False)


@contextmanager
def engine_memory(memory):
    with with_agent_checkpointer_override(memory.saver):
        yield


def agent(name: str, model: Scripted, agents: list[Agent] | None = None) -> Agent:
    # Built like module factories build them: memory=None, no engine handle.
    return Agent(
        name=name,
        description=f"{name} agent.",
        chat_model=model,
        agents=agents,
        memory=None,
        configuration=AgentConfiguration(system_prompt=f"You are {name}."),
    )


def turn(template: Agent, prompt: str, thread_id: str = "conversation") -> str:
    # As Nexus and the OpenAI gateway run a request: a duplicate of the cached
    # template with a fresh state on the conversation's thread.
    scoped = template.duplicate(
        agent_shared_state=AgentSharedState(thread_id=thread_id)
    )
    return scoped.invoke(prompt)


def remembers_across_turns(memory) -> dict[str, Any]:
    model = Scripted(replies=[AIMessage("noted"), AIMessage("Bob")])
    with engine_memory(memory):
        first = turn(agent("Memo", model), "my name is Bob")
    memory.restart()
    with engine_memory(memory):
        second = turn(agent("Memo", model), "what is my name?")
    return {"outputs": [first, second], "model": model.received}


def handoff_continues_with_the_sub_agent(memory) -> dict[str, Any]:
    lead = Scripted(replies=[handoff("Helper")])
    helper = Scripted(replies=[AIMessage("hi Bob"), AIMessage("you are Bob")])

    def tree() -> Agent:
        return agent("Lead", lead, agents=[agent("Helper", helper)])

    with engine_memory(memory):
        first = turn(tree(), "my name is Bob")
    memory.restart()
    with engine_memory(memory):
        second = turn(tree(), "who am I?")
    return {
        "outputs": [first, second],
        "lead": lead.received,
        "helper": helper.received,
    }


def sub_agent_continues_its_supervisors_thread(memory) -> dict[str, Any]:
    lead = Scripted(replies=[handoff("Helper")])
    helper = Scripted(replies=[AIMessage("hi Bob"), AIMessage("you are Bob")])
    with engine_memory(memory):
        first = turn(agent("Lead", lead, agents=[agent("Helper", helper)]), "I am Bob")
    memory.restart()
    with engine_memory(memory):
        second = turn(agent("Helper", helper), "who am I?")
    return {"outputs": [first, second], "helper": helper.received}


def another_agent_takes_over_the_thread(memory) -> dict[str, Any]:
    first_model = Scripted(replies=[AIMessage("noted")])
    second_model = Scripted(replies=[AIMessage("Bob")])
    with engine_memory(memory):
        first = turn(agent("First", first_model), "my name is Bob")
    memory.restart()
    with engine_memory(memory):
        second = turn(agent("Second", second_model), "what is my name?")
    return {"outputs": [first, second], "second": second_model.received}


@pytest.fixture
def transcripts(tmp_path):
    def run(scenario) -> tuple[dict[str, Any], dict[str, Any]]:
        today = SharedSaver(tmp_path / "today")
        engine = EngineDocuments(tmp_path)
        try:
            return scenario(today), scenario(engine)
        finally:
            engine.close()

    return run


def test_memory_survives_a_restart(transcripts):
    today, engine = transcripts(remembers_across_turns)
    assert engine == today
    assert engine["model"][1] == ["my name is Bob", "noted", "what is my name?"]


def test_a_handoff_survives_a_restart_and_routes_to_the_sub_agent(transcripts):
    today, engine = transcripts(handoff_continues_with_the_sub_agent)
    assert engine == today
    assert engine["outputs"] == ["hi Bob", "you are Bob"]
    assert len(engine["lead"]) == 1  # turn two went straight to the sub-agent
    assert "my name is Bob" in engine["helper"][1]


def test_a_sub_agent_invoked_directly_continues_its_supervisors_thread(transcripts):
    # Needs one scope across agents: the sub-agent reads the thread its
    # supervisor wrote, as with the shared PostgresSaver.
    today, engine = transcripts(sub_agent_continues_its_supervisors_thread)
    assert engine == today
    assert "I am Bob" in engine["helper"][1]


def test_another_top_level_agent_on_the_thread_behaves_as_today(transcripts):
    # Today the second agent resumes routing to the first agent's node, which
    # its graph lacks, and the turn ends without calling a model. Preserved
    # as is: changing it is a routing decision, not a storage one.
    today, engine = transcripts(another_agent_takes_over_the_thread)
    assert engine == today


def test_intent_agents_use_the_engine_memory_too(tmp_path):
    memory = EngineDocuments(tmp_path)
    try:
        with engine_memory(memory):
            intent_agent = IntentAgent(
                name="Router",
                description="Routes.",
                chat_model=Scripted(replies=[AIMessage("ok")]),
                embedding_model=DeterministicFakeEmbedding(size=8),
                enable_default_intents=False,
                memory=None,
            )
        assert intent_agent._checkpointer is memory.saver
    finally:
        memory.close()


def test_agents_outside_an_engine_keep_their_standalone_memory():
    model = Scripted(replies=[AIMessage("noted"), AIMessage("Bob")])
    standalone = agent("Memo", model)
    assert isinstance(standalone._checkpointer, InMemorySaver)
    turn(standalone, "my name is Bob")
    turn(standalone, "what is my name?")
    assert model.received[1] == ["my name is Bob", "noted", "what is my name?"]
