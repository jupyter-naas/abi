"""The platform tools act for the user who is chatting.

They reach the kernel services in the chatting user's ``CallContext``, so the
user's policy applies to what they return. The kernel service here is a stand-in
that checks with IAM the way a domain service does (``ServiceGuard``), wired
with a real ``IAMService``; the agent turn runs the real graph, through the
same thread hops as a Nexus chat stream.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    current_call_context,
)
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.iam.tests.authorization_contract import (
    contract_iam,
    wire,
)
from naas_abi_core.services.iam.tests.iam_harness import (
    TRIPLE_STORE,
    IAMHarness,
    statement,
)
from naas_abi_core.services.ServiceBase import ServiceBase
from naas_abi_core.services.triple_store.TripleStorePorts import QueryStream

from naas_abi.tools import platform_tools

SALES = "http://ontology.naas.ai/graph/sales"
HR = "http://ontology.naas.ai/graph/hr"


class _GuardedTripleStore(ServiceBase):
    """Lists and queries graphs the caller may see, as a domain service would."""

    def __init__(self) -> None:
        super().__init__()
        self._guard = ServiceGuard.of(TRIPLE_STORE, self)
        self.seen: list[CallContext] = []

    def list_graphs(self) -> list[str]:
        self.seen.append(current_call_context())
        return self._guard.filter("ListGraphs", "graph", [SALES, HR], lambda g: g)

    @contextmanager
    def query_stream(self, sparql: str):
        self.seen.append(current_call_context())
        self._guard.require("Query", "graph", HR)
        yield QueryStream("ASK", ask_answer=True)


def _graph(iri: str) -> str:
    return ServiceGuard(TRIPLE_STORE, lambda: None).name("graph", iri)


def _setup(monkeypatch):
    iam = contract_iam()
    iam._register_catalog(TRIPLE_STORE)
    store = wire(_GuardedTripleStore(), iam)
    monkeypatch.setattr(
        platform_tools, "_services", lambda: SimpleNamespace(triple_store=store)
    )
    tools = {t.name: t for t in platform_tools.platform_service_tools()}
    return IAMHarness(iam), store, tools


def test_a_tool_returns_only_what_the_chatting_user_may_see(monkeypatch):
    h, _, tools = _setup(monkeypatch)
    alice, bob = h.user("alice"), h.user("bob")
    h.grant(alice.id, statement("Allow", ["triple_store:ListGraphs"], [_graph(SALES)]))

    with h.as_(actor="api", on_behalf_of=alice):
        assert tools["kg_list_graphs"].invoke({}) == [SALES]
    with h.as_(actor="api", on_behalf_of=bob):
        assert tools["kg_list_graphs"].invoke({}) == []
    with as_service_account("engine"):
        assert tools["kg_list_graphs"].invoke({}) == [SALES, HR]


def test_a_tool_cannot_reach_a_resource_the_user_may_not_see(monkeypatch):
    h, _, tools = _setup(monkeypatch)
    alice, bob = h.user("alice"), h.user("bob")
    h.grant(alice.id, statement("Allow", ["triple_store:Query"], [_graph(HR)]))

    with h.as_(actor="api", on_behalf_of=bob):
        refused = tools["kg_sparql_query"].invoke({"query": "ASK {}"})
    assert "error" in refused and "not found" in refused["error"]
    with h.as_(actor="api", on_behalf_of=alice):
        assert tools["kg_sparql_query"].invoke({"query": "ASK {}"}) == {"ask": True}


class _ScriptedChatModel(BaseChatModel):
    """Asks for one tool, then answers."""

    script: list[AIMessage]
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> _ScriptedChatModel:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        index = min(self.calls, len(self.script) - 1)
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=self.script[index])])


def _agent(tools: dict) -> Agent:
    return Agent(
        name="platform_services_under_test",
        description="Calls a platform tool for the chatting user",
        chat_model=_ScriptedChatModel(
            script=[
                AIMessage(
                    content="",
                    tool_calls=[{"name": "kg_list_graphs", "args": {}, "id": "c1"}],
                ),
                AIMessage(content="done"),
            ]
        ),
        tools=[tools["kg_list_graphs"]],
        agents=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="platform-tools"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )


def test_an_agent_turn_calls_the_tools_as_the_chatting_user(monkeypatch):
    """The Nexus chat path: the request's context, then ``asyncio.to_thread``
    pulls ``stream_invoke``, whose run thread executes the graph and its tools."""
    h, store, tools = _setup(monkeypatch)
    alice = h.user("alice")
    h.grant(alice.id, statement("Allow", ["triple_store:ListGraphs"], [_graph(SALES)]))
    agent = _agent(tools)

    async def chat() -> list[dict]:
        # As Nexus reads it: one ``next`` per thread hop, until ``done``.
        stream = iter(agent.stream_invoke("which graphs?"))
        events = []
        while True:
            event = await asyncio.to_thread(next, stream)
            events.append(event)
            if event["event"] == "done":
                return events

    with h.as_(actor="api", on_behalf_of=alice):
        events = asyncio.run(chat())

    (seen,) = store.seen
    assert seen.principal.name == "api"
    assert seen.on_behalf_of is not None and seen.on_behalf_of.id == alice.id
    responses = [e["data"] for e in events if e["event"] == "tool_response"]
    assert responses and SALES in responses[0] and HR not in responses[0]


def test_an_agent_turn_with_no_caller_reaches_nothing(monkeypatch):
    """No context, no identity: the kernel denies (anonymous calls are refused)."""
    h, store, tools = _setup(monkeypatch)
    h.grant(
        h.user("alice").id,
        statement("Allow", ["triple_store:ListGraphs"], [_graph(SALES)]),
    )
    events = list(_agent(tools).stream_invoke("which graphs?"))

    (seen,) = store.seen
    assert seen.principal.kind == "anonymous"
    responses = [e["data"] for e in events if e["event"] == "tool_response"]
    assert responses and SALES not in responses[0]
