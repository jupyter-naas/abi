"""End-to-end smoke test for CoordinatorAgent with real sub-agents and an LLM.

The three use cases below mirror what the user asked to verify in chat with Abi:

1. **Capabilities listing** — "what can you do?" should be answered by the
   coordinator itself (RAW intent or templated refusal), NOT routed to a
   subagent that would answer with its own voice.
2. **Direct routing to a subagent** — "search news about AI" should land in
   the news subagent, which then responds as itself (no "the task has been
   transferred to me" parroting).
3. **Multi-turn handoff with prior coordinator prose** — the coordinator
   refuses, suggests options, the user picks one. The subagent that takes
   over should answer the *original* question without echoing the
   coordinator's suggestion-list voice.

The tests are gated on `OPENAI_API_KEY`. We use `gpt-4.1-mini` to keep the
cost low; this matches AbiAgent's default. The test budget is ~5 prompts per
fixture so total spend is small.
"""

from __future__ import annotations

import os
from queue import Queue

import pytest
from langchain_openai import ChatOpenAI

from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration
from naas_abi_core.services.agent.beta.IntentMapper import (
    Intent,
    IntentScope,
    IntentType,
)
from naas_abi_core.services.agent.CoordinatorAgent import CoordinatorAgent
from naas_abi_core.services.agent.IntentAgent import AgentSharedState

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping LLM-backed smoke test",
)


def _make_subagent(name: str, description: str, system_prompt: str) -> Agent:
    """Build a minimal sub-agent — no tools, just a chat model and a prompt.

    NOTE: we MUST pass an explicit `state=AgentSharedState(...)`. `Agent.__init__`
    declares `state: AgentSharedState = AgentSharedState()` as a default, which
    is the classic Python mutable-default gotcha — every call without an explicit
    `state=` shares the same singleton instance, and leaks `current_active_agent`
    state across tests (and across production requests). See the analysis at
    the end of this PR for a recommended framework fix.
    """
    model = ChatOpenAI(model="gpt-4.1-mini")
    return Agent(
        name=name,
        description=description,
        chat_model=model,
        tools=[],
        agents=[],
        configuration=AgentConfiguration(system_prompt=system_prompt),
        state=AgentSharedState(thread_id=f"sub-{name}"),
    )


@pytest.fixture
def coordinator() -> CoordinatorAgent:
    """A CoordinatorAgent with two clearly differentiated sub-agents.

    NewsAgent: pretends to know about current events.
    MathAgent: solves arithmetic.
    """
    model = ChatOpenAI(model="gpt-4.1-mini")

    news_agent = _make_subagent(
        name="NewsAgent",
        description="Specialist that summarises current news and headlines.",
        system_prompt=(
            "You are NewsAgent. Reply concisely with 2-3 plausible headlines on "
            "the topic the user asks about. Start your answer with 'NewsAgent:'. "
            "Never apologise for being a synthetic agent; just give the headlines."
        ),
    )
    math_agent = _make_subagent(
        name="MathAgent",
        description="Specialist that evaluates arithmetic expressions step by step.",
        system_prompt=(
            "You are MathAgent. Solve the arithmetic the user provides. Show one "
            "line of reasoning then the final number. Start your answer with "
            "'MathAgent:'."
        ),
    )

    intents = [
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="search news about a topic",
            intent_target="NewsAgent",
            intent_scope=IntentScope.DIRECT,
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="give me the latest headlines",
            intent_target="NewsAgent",
            intent_scope=IntentScope.DIRECT,
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="solve an arithmetic problem",
            intent_target="MathAgent",
            intent_scope=IntentScope.DIRECT,
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="calculate a number",
            intent_target="MathAgent",
            intent_scope=IntentScope.DIRECT,
        ),
    ]

    shared_state = AgentSharedState(thread_id="test-thread")
    coord = CoordinatorAgent(
        name="Abi",
        description="Coordinator that routes to NewsAgent or MathAgent.",
        chat_model=model,
        tools=[],
        agents=[news_agent, math_agent],
        intents=intents,
        memory=None,
        state=shared_state,
        configuration=AgentConfiguration(
            system_prompt=(
                "<role>You are Abi, a routing coordinator.</role>\n"
                "<agents>\n- NewsAgent\n- MathAgent\n</agents>"
            )
        ),
        event_queue=Queue(),
        markdown_pretty_display=False,
        # Test fixture uses lighter intent values than production AbiAgent — drop
        # the threshold to 0.70 so realistic vector-search confidences (typical
        # mid-70s for paraphrases) still trigger direct routing.
        threshold=0.70,
        direct_intent_score=0.75,
    )
    return coord


# --------------------------------------------------------------------------- #
# Use case 1 — Capabilities & greetings answered by the coordinator itself    #
# --------------------------------------------------------------------------- #


def test_uc1_greeting_handled_by_coordinator(coordinator: CoordinatorAgent) -> None:
    """RAW intent 'hello' returns the default greeting — no subagent voice."""
    result = coordinator.invoke("hello")
    assert result is not None and result != ""
    assert "NewsAgent" not in result, result
    assert "MathAgent" not in result, result


def test_uc1_thanks_handled_by_coordinator(coordinator: CoordinatorAgent) -> None:
    """RAW intent 'thank you' returns the default ack — no subagent voice."""
    result = coordinator.invoke("thank you")
    assert result is not None and result != ""
    assert "NewsAgent" not in result, result
    assert "MathAgent" not in result, result


def test_uc1_no_match_returns_coordinator_refusal(
    coordinator: CoordinatorAgent,
) -> None:
    """A request neither agent can satisfy hits the coordinator_refusal node."""
    result = coordinator.invoke(
        "Please paint me a portrait of a tabby cat in oils on canvas."
    )
    assert result is not None and result != ""
    # Templated refusal — NOT a free-form LLM answer pretending to act.
    refusal_signals = [
        "I cannot handle",
        "I couldn't route",
        "delegate to",
        "address one of them",
        "specialised agents",
    ]
    assert any(s in result for s in refusal_signals), result


# --------------------------------------------------------------------------- #
# Use case 2 — Direct routing: subagent answers as ITSELF                     #
# --------------------------------------------------------------------------- #


def test_uc2_news_request_routes_to_news_agent(
    coordinator: CoordinatorAgent,
) -> None:
    """Verify the news subagent answers in its own voice — not as a parrot."""
    result = coordinator.invoke("give me the latest headlines about AI")
    assert result is not None and result != ""
    # The subagent's system prompt instructs it to start with 'NewsAgent:'.
    assert "NewsAgent:" in result, (
        f"Expected NewsAgent to answer as itself; got: {result!r}"
    )
    # And it should NOT parrot any routing language.
    forbidden = [
        "transferred to me",
        "routed to me",
        "the task has been",
        "I've been asked to",
        "I will transfer",
    ]
    lowered = result.lower()
    assert not any(p in lowered for p in forbidden), (
        f"Subagent parroted routing language: {result!r}"
    )


def test_uc2_math_request_routes_to_math_agent(
    coordinator: CoordinatorAgent,
) -> None:
    """Verify the math subagent answers in its own voice."""
    # Start a fresh thread so prior conversation state doesn't influence routing.
    coordinator.state.set_thread_id("test-uc2-math")
    result = coordinator.invoke("solve 17 * 24 for me please")
    assert result is not None and result != ""
    assert "MathAgent:" in result, (
        f"Expected MathAgent to answer as itself; got: {result!r}"
    )
    # And the actual answer should be in the response (17*24 = 408).
    assert "408" in result, f"MathAgent didn't compute correctly: {result!r}"


# --------------------------------------------------------------------------- #
# Use case 3 — Multi-turn: coordinator suggestion → subagent answers cleanly  #
# --------------------------------------------------------------------------- #


def test_uc3_multi_turn_handoff_after_coordinator_prose(
    coordinator: CoordinatorAgent,
) -> None:
    """After the coordinator emits an AIMessage, the subagent must NOT parrot it.

    We exercise this by:
    1. Asking something the coordinator can answer (greeting).
    2. Then asking something that routes to NewsAgent.
    3. Checking the subagent's reply is in its own voice, not echoing turn-1
       coordinator content.
    """
    coordinator.state.set_thread_id("test-uc3-multi-turn")

    turn1 = coordinator.invoke("hello")
    assert "NewsAgent" not in turn1, turn1
    assert "MathAgent" not in turn1, turn1

    turn2 = coordinator.invoke("give me the latest headlines about robotics")
    assert "NewsAgent:" in turn2, (
        f"Expected NewsAgent to answer turn-2 as itself; got: {turn2!r}"
    )
    # Routing-language guard.
    forbidden = [
        "transferred to me",
        "routed to me",
        "the task has been",
        "I will transfer",
        "Hello, what can I do for you?",  # parroting turn-1 coordinator text
    ]
    lowered = turn2.lower()
    assert not any(p.lower() in lowered for p in forbidden), (
        f"Subagent parroted routing/coordinator language in turn-2: {turn2!r}"
    )
