"""A copy of an agent made for one caller (``Agent.duplicate(keep=)``) leaves out
the sub-agents the caller may not use: no handoff tool, no bound tool, no graph
node, no intent route to them; and a handoff or an intent the template still
knows is refused at run time."""

from __future__ import annotations

import hashlib
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.agent.beta.IntentMapper import Intent, IntentType
from naas_abi_core.services.agent.IntentAgent import IntentAgent


class _Model(BaseChatModel):
    """Answers "done"; ``bound`` names the tools it was bound with."""

    bound: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "keep-test"

    def bind_tools(self, tools: Any, **kwargs: Any) -> _Model:
        del kwargs
        return self.model_copy(
            update={"bound": [getattr(t, "name", "") for t in tools]}
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Any = None,
        run_manager: Any = None,
        **kw: Any,
    ) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="done"))]
        )


class _Words(Embeddings):
    """The same text, the same vector: an intent matches its own words."""

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * 64
        for word in text.lower().split():
            vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % 64] += 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@tool
def lookup(query: str) -> str:
    """Look something up.

    Args:
        query (str): What to look up.
    """
    return query


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


def _lead() -> IntentAgent:
    return IntentAgent(
        name="Lead",
        description="Routes to its sub-agents.",
        chat_model=_Model(),
        embedding_model=_Words(),
        tools=[lookup],
        agents=[_child("Alpha"), _child("Beta")],
        intents=[
            Intent("talk to alpha", IntentType.AGENT, "Alpha"),
            Intent("talk to beta", IntentType.AGENT, "Beta"),
        ],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="t"),
        configuration=AgentConfiguration(system_prompt="You route."),
        enable_default_intents=False,
        enable_default_tools=False,
    )


def _without_beta(agent: Agent) -> bool:
    return agent.name != "Beta"


def test_a_left_out_sub_agent_has_no_tool_bound_tool_or_node():
    lead = _lead()
    assert "transfer_to_Beta" in lead._chat_model_with_tools.bound  # type: ignore[attr-defined]
    copy = lead.duplicate(keep=_without_beta)

    assert [a.name for a in copy._agents] == ["Alpha"]
    assert "transfer_to_Beta" not in copy._tools_by_name
    assert "transfer_to_Alpha" in copy._tools_by_name
    bound = copy._chat_model_with_tools.bound  # type: ignore[attr-defined]
    assert "transfer_to_Beta" not in bound and {"transfer_to_Alpha", "lookup"} <= set(
        bound
    )
    nodes = set(copy.graph.get_graph().nodes)
    assert "Beta" not in nodes and "Alpha" in nodes
    # The template is untouched.
    assert "transfer_to_Beta" in lead._tools_by_name


def test_an_intent_to_a_left_out_sub_agent_does_not_route_to_it():
    copy = _lead().duplicate(keep=_without_beta)
    assert [i.intent_target for i in copy._intents] == ["Alpha"]

    to_beta = copy.map_intents({"messages": [HumanMessage(content="talk to beta")]})
    assert to_beta.goto != "Beta"
    assert all(
        m["intent"].intent_target != "Beta"
        for m in (to_beta.update or {}).get("intent_mapping", {}).get("intents", [])
    )
    to_alpha = copy.map_intents({"messages": [HumanMessage(content="talk to alpha")]})
    mapped = (to_alpha.update or {}).get("intent_mapping", {}).get("intents", [])
    assert [m["intent"].intent_target for m in mapped] == ["Alpha"]

    # The router refuses one even if a stale mapping names it.
    beta = Intent("talk to beta", IntentType.AGENT, "Beta")
    routed = copy.intent_mapping_router(
        {
            "intent_mapping": {"intents": [{"intent": beta, "score": 1.0}]},
            "messages": [],
        }
    )
    assert routed.goto == "call_model"


def test_a_handoff_to_an_agent_that_is_no_sub_agent_is_refused():
    copy = _lead().duplicate(keep=_without_beta)
    # A stale handoff tool, as a template wired before the narrowing had.
    copy._tools_by_name["transfer_to_Beta"] = _lead()._tools_by_name["transfer_to_Beta"]
    call = {"name": "transfer_to_Beta", "args": {}, "id": "c1", "type": "tool_call"}
    commands = copy.call_tools({"messages": [AIMessage(content="", tool_calls=[call])]})
    message = commands[0].update["messages"][0]
    assert "not available" in message.content
    assert copy.state.current_active_agent != "Beta"


def test_without_keep_every_sub_agent_is_copied():
    copy = _lead().duplicate()
    assert [a.name for a in copy._agents] == ["Alpha", "Beta"]
    assert "transfer_to_Beta" in copy._tools_by_name
