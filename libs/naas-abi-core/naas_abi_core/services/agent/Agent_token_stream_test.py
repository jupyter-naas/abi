"""Token streaming: the answer reaches ``stream_invoke`` while the model writes it.

A scripted model streams chunks through the real graph. What is checked is what
a chat client sees: ``ai_message_delta`` text, then the ``ai_message`` of the
same message, whose text the deltas add up to.
"""

from __future__ import annotations

import time
from functools import reduce
from operator import add
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, message_chunk_to_message
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    AnswerReleaseGate,
)
from naas_abi_core.services.agent.context import agent_answer_holdback_chars
from pydantic import Field

LONG = [f"Sentence number {i} is part of the answer. " for i in range(12)]
SHORT = [
    "Paris is the capital of France, ",
    "with about two million people ",
    "in the city.",
]


class Streaming(BaseChatModel):
    """Streams scripted replies, one per call (the last one repeats)."""

    replies: list[list[AIMessageChunk]]
    calls: int = 0
    delay: float = 0.0
    fail_after: int | None = None
    stopped_early: list[bool] = Field(default_factory=list)
    bound: list[list[str]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "streaming-scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Streaming:
        self.bound.append([getattr(t, "name", "") for t in tools])
        return self

    def _next(self) -> list[AIMessageChunk]:
        self.calls += 1
        return self.replies[min(self.calls, len(self.replies)) - 1]

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        merged = reduce(add, self._next())
        message = message_chunk_to_message(merged)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        chunks = self._next()
        served = 0
        try:
            for chunk in chunks:
                if self.fail_after is not None and served == self.fail_after:
                    raise RuntimeError("upstream connection reset")
                if self.delay:
                    time.sleep(self.delay)
                served += 1
                yield ChatGenerationChunk(message=chunk.model_copy())
        finally:
            self.stopped_early.append(served < len(chunks))


class NoStream(Streaming):
    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError("no streaming here")
        yield  # pragma: no cover


def text(*pieces: str) -> list[AIMessageChunk]:
    return [AIMessageChunk(content=piece) for piece in pieces]


def calls_tool(name: str, preamble: str = "", args: str = "{}") -> list[AIMessageChunk]:
    chunks = text(preamble) if preamble else []
    return chunks + [
        AIMessageChunk(
            content="",
            tool_call_chunks=[{"name": name, "args": args, "id": "call-1", "index": 0}],
        )
    ]


@tool
def add_one(input: int) -> int:
    """Add one to the input."""
    return input + 1


@pytest.fixture(autouse=True)
def _standalone(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)


def make_agent(
    name: str,
    model: BaseChatModel,
    *,
    tools: list | None = None,
    agents: list[Agent] | None = None,
    saver: InMemorySaver | None = None,
    supervised: bool = False,
) -> Agent:
    return Agent(
        name=name,
        description=f"{name} agent.",
        chat_model=model,
        tools=tools or [],
        agents=agents,
        memory=saver or InMemorySaver(),
        state=AgentSharedState(supervisor_agent=name if supervised else None),
        configuration=AgentConfiguration(system_prompt=f"You are {name}."),
    )


def run(agent: Agent, prompt: str = "hello") -> list[dict[str, Any]]:
    scoped = agent.duplicate(
        agent_shared_state=AgentSharedState(
            thread_id="conversation", supervisor_agent=agent.state.supervisor_agent
        )
    )
    return list(scoped.stream_invoke(prompt))


def deltas(events: list[dict[str, Any]]) -> list[str]:
    return [e["data"] for e in events if e["event"] == "ai_message_delta"]


def ai_messages(events: list[dict[str, Any]]) -> list[str]:
    return [e["data"] for e in events if e["event"] == "ai_message"]


def first_index(events: list[dict[str, Any]], name: str) -> int:
    return next(i for i, e in enumerate(events) if e["event"] == name)


# ---------------------------------------------------------------------------
# Through the graph
# ---------------------------------------------------------------------------


def test_an_answer_streams_as_deltas_that_add_up_to_the_message():
    events = run(make_agent("Lead", Streaming(replies=[text(*LONG)])))

    assert len(deltas(events)) > 3
    assert "".join(deltas(events)) == "".join(LONG)
    assert ai_messages(events) == ["".join(LONG)]
    assert first_index(events, "ai_message_delta") < first_index(events, "ai_message")


def test_a_short_answer_comes_whole_in_its_ai_message():
    events = run(make_agent("Lead", Streaming(replies=[text("Hi ", "there.")])))

    assert deltas(events) == []
    assert ai_messages(events) == ["Hi there."]


def test_the_line_before_a_tool_call_is_not_streamed():
    model = Streaming(
        replies=[
            calls_tool("add_one", "Let me compute that.", '{"input": 1}'),
            text(*LONG),
        ]
    )
    events = run(make_agent("Lead", model, tools=[add_one]))

    assert "".join(deltas(events)) == "".join(LONG)
    assert first_index(events, "tool_usage") < first_index(events, "ai_message_delta")
    assert first_index(events, "tool_response") < first_index(
        events, "ai_message_delta"
    )
    assert not any("Let me" in d for d in deltas(events))


def test_a_sub_agent_answer_streams_after_a_handoff():
    saver = InMemorySaver()
    lead = Streaming(replies=[calls_tool("transfer_to_Helper", "One moment.")])
    helper = Streaming(replies=[text(*LONG)])
    tree = make_agent(
        "Lead",
        lead,
        agents=[make_agent("Helper", helper, saver=saver)],
        saver=saver,
        supervised=True,
    )

    events = run(tree)

    assert "".join(deltas(events)) == "".join(LONG)
    assert ai_messages(events) == ["".join(LONG)]
    assert not any("One moment" in d for d in deltas(events))


def test_text_tool_markup_is_never_streamed():
    markup = [
        (
            "I will call the tool now, as the user asked me to do it right away "
            "and with no further delay. "
        ),
        "<tool_",
        'call>{"name": "add_one", "arguments": {"input": 1}}</tool_call>',
    ]
    model = Streaming(replies=[text(*markup), text("Two.")])
    events = run(make_agent("Lead", model, tools=[add_one]))

    assert not any("tool_call" in d or "<tool" in d for d in deltas(events))


def test_a_model_that_cannot_stream_is_invoked():
    events = run(make_agent("Lead", NoStream(replies=[text(*LONG)])))

    assert deltas(events) == []
    assert ai_messages(events) == ["".join(LONG)]


def test_an_error_after_text_was_shown_ends_the_answer_with_it():
    model = Streaming(replies=[text(*LONG)], fail_after=9)
    events = run(make_agent("Lead", model))

    streamed = "".join(deltas(events))
    assert streamed.startswith("".join(LONG[:6]))
    assert streamed.endswith("upstream connection reset")
    assert ai_messages(events) == [streamed]


def test_a_consumer_that_leaves_stops_the_model():
    model = Streaming(replies=[text(*(LONG * 4))], delay=0.02)
    agent = make_agent("Lead", model).duplicate(
        agent_shared_state=AgentSharedState(thread_id="conversation")
    )

    stream = agent.stream_invoke("hello")
    for event in stream:
        if event["event"] == "ai_message_delta":
            break
    stream.close()

    deadline = time.monotonic() + 5
    while not model.stopped_early and time.monotonic() < deadline:
        time.sleep(0.02)
    assert model.stopped_early == [True]

    # The next turn on the same agent is not cancelled and carries none of the
    # cut turn's text, streamed, whole or replayed.
    again = [f"Second answer, part {i}. " for i in range(12)]
    model.replies.append(text(*again))
    model.delay = 0.0
    events = list(agent.stream_invoke("again"))
    assert "".join(deltas(events)) == "".join(again)
    assert ai_messages(events) == ["".join(again)]
    replay = "\n".join(e["data"] for e in events if e["event"] == "message")
    assert replay == "".join(again)


# ---------------------------------------------------------------------------
# Voice-call hold (``agent_answer_holdback_chars``)
# ---------------------------------------------------------------------------


@pytest.fixture
def voice_hold():
    token = agent_answer_holdback_chars.set(60)
    yield
    agent_answer_holdback_chars.reset(token)


def test_a_short_answer_streams_on_a_voice_call(voice_hold):
    events = run(make_agent("Lead", Streaming(replies=[text(*SHORT)])))

    assert len(deltas(events)) > 1
    assert "".join(deltas(events)) == "".join(SHORT)


def test_the_same_answer_comes_whole_without_the_voice_hold():
    events = run(make_agent("Lead", Streaming(replies=[text(*SHORT)])))

    assert deltas(events) == []


def test_on_a_voice_call_the_filler_before_a_tool_call_is_not_streamed(voice_hold):
    model = Streaming(
        replies=[
            calls_tool("add_one", "Let me check that for you.", '{"input": 1}'),
            text(*SHORT),
        ]
    )
    events = run(make_agent("Lead", model, tools=[add_one]))

    assert "".join(deltas(events)) == "".join(SHORT)
    assert not any("Let me" in d for d in deltas(events))


def test_on_a_voice_call_the_filler_before_a_handoff_is_not_streamed(voice_hold):
    saver = InMemorySaver()
    lead = Streaming(
        replies=[calls_tool("transfer_to_Helper", "One moment, I'll ask Helper.")]
    )
    tree = make_agent(
        "Lead",
        lead,
        agents=[make_agent("Helper", Streaming(replies=[text(*SHORT)]), saver=saver)],
        saver=saver,
        supervised=True,
    )

    events = run(tree)

    assert "".join(deltas(events)) == "".join(SHORT)
    assert not any("One moment" in d for d in deltas(events))


# ---------------------------------------------------------------------------
# Duplicating with a roster
# ---------------------------------------------------------------------------


def test_a_dropped_sub_agent_gets_no_handoff_tool_at_any_depth():
    lead = Streaming(replies=[text("Hi.")])
    helper = Streaming(replies=[text("Hi.")])
    template = make_agent(
        "Lead",
        lead,
        agents=[
            make_agent(
                "Helper",
                helper,
                agents=[make_agent("Nested", Streaming(replies=[text("Hi.")]))],
            ),
            make_agent("Other", Streaming(replies=[text("Hi.")])),
        ],
    )

    clone = template.duplicate(keep_agent=lambda sub: sub.name in {"Helper"})

    assert [sub.name for sub in clone._agents] == ["Helper"]
    assert [sub.name for sub in clone._agents[0]._agents] == []
    assert "transfer_to_Other" not in lead.bound[-1]
    assert "transfer_to_Helper" in lead.bound[-1]
    assert "transfer_to_Nested" not in helper.bound[-1]
    assert "transfer_to_Other" in template._tools_by_name


# ---------------------------------------------------------------------------
# AnswerReleaseGate
# ---------------------------------------------------------------------------


def test_gate_holds_text_until_it_is_long_enough():
    gate = AnswerReleaseGate(10)

    assert gate.feed("Hello") == ""
    assert gate.feed(" world!") == "Hello world!"
    assert gate.feed(" More.") == " More."
    assert gate.finish("Hello world! More. End.") == " End."


def test_gate_releases_nothing_after_a_tool_call():
    gate = AnswerReleaseGate(10)
    gate.feed("Let me check that for you.")
    gate.block()

    assert gate.feed(" more") == ""
    assert gate.finish("anything") == ""


def test_gate_does_not_count_think_blocks():
    gate = AnswerReleaseGate(10)

    assert gate.feed("<think>a long private thought here</think>") == ""
    assert gate.feed("Hi") == ""
    assert gate.feed(" there, friend") == (
        "<think>a long private thought here</think>Hi there, friend"
    )


def test_gate_holds_what_may_start_text_tool_markup():
    gate = AnswerReleaseGate(5)

    assert gate.feed("Answer is here <tool") == "Answer is here "
    assert gate.feed("_call>{}") == ""
    assert gate.blocked
