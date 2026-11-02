"""Token streaming through ``stream_with_abi_inprocess`` and the remote path.

A real core ``Agent`` runs on a scripted streaming model; the test reads what
``emit_stream`` would turn into ``{"content": ...}`` frames (the ``str``
chunks) and checks they arrive as many deltas whose sum is the answer, once.
"""

from __future__ import annotations

import asyncio
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
from naas_abi.apps.nexus.apps.api.app.services import provider_runtime
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.streaming import (
    remote_agent_chunks,
)
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    AgentEventChunks,
    Message,
    ProviderConfig,
    stream_with_abi_inprocess,
)
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from pydantic import Field

LONG = [f"Sentence number {i} is part of the answer. " for i in range(12)]


class Streaming(BaseChatModel):
    replies: list[list[AIMessageChunk]]
    calls: int = 0
    delay: float = 0.0
    stopped_early: list[bool] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "streaming-scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Streaming:
        return self

    def _next(self) -> list[AIMessageChunk]:
        self.calls += 1
        return self.replies[min(self.calls, len(self.replies)) - 1]

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        message = message_chunk_to_message(reduce(add, self._next()))
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        chunks = self._next()
        served = 0
        try:
            for chunk in chunks:
                if self.delay:
                    time.sleep(self.delay)
                served += 1
                yield ChatGenerationChunk(message=chunk.model_copy())
        finally:
            self.stopped_early.append(served < len(chunks))


def text(*pieces: str) -> list[AIMessageChunk]:
    return [AIMessageChunk(content=piece) for piece in pieces]


def calls_tool(name: str, preamble: str, args: str = "{}") -> list[AIMessageChunk]:
    return text(preamble) + [
        AIMessageChunk(
            content="",
            tool_call_chunks=[{"name": name, "args": args, "id": "call-1", "index": 0}],
        )
    ]


@tool
def add_one(input: int) -> int:
    """Add one to the input."""
    return input + 1


def make_agent(name: str, model: BaseChatModel, **kwargs: Any) -> Agent:
    supervised = kwargs.pop("supervised", False)
    return Agent(
        name=name,
        description=f"{name} agent.",
        chat_model=model,
        memory=kwargs.pop("saver", None) or InMemorySaver(),
        state=AgentSharedState(supervisor_agent=name if supervised else None),
        configuration=AgentConfiguration(system_prompt=f"You are {name}."),
        **kwargs,
    )


@pytest.fixture(autouse=True)
def _standalone(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.setattr(provider_runtime, "resolve_inprocess_llm_model_for_turn", lambda *_: None)


CONFIG = ProviderConfig(
    id="p1",
    name="Abi",
    type="abi",
    enabled=True,
    endpoint="inprocess://abi",
    api_key=None,
    account_id=None,
    model="Abi",
)


def serve(monkeypatch, template: Agent) -> None:
    monkeypatch.setattr(provider_runtime, "_resolve_inprocess_abi_agent", lambda _name: template)


async def chunks_of(**kwargs: Any) -> list[str | dict[str, Any]]:
    return [
        chunk
        async for chunk in stream_with_abi_inprocess(
            [Message(role="user", content="hello")],
            CONFIG,
            thread_id="conv-1",
            user_context_preamble=None,
            **kwargs,
        )
    ]


def texts(chunks: list[str | dict[str, Any]]) -> list[str]:
    return [c for c in chunks if isinstance(c, str)]


@pytest.mark.asyncio
async def test_an_answer_reaches_the_chat_as_deltas_said_once(monkeypatch):
    serve(monkeypatch, make_agent("Abi", Streaming(replies=[text(*LONG)])))

    chunks = await chunks_of()

    assert len(texts(chunks)) > 3
    assert "".join(texts(chunks)) == "".join(LONG)


@pytest.mark.asyncio
async def test_tool_steps_come_before_the_streamed_answer(monkeypatch):
    model = Streaming(replies=[calls_tool("add_one", "Let me add.", '{"input": 1}'), text(*LONG)])
    serve(monkeypatch, make_agent("Abi", model, tools=[add_one]))

    chunks = await chunks_of()

    first_text = next(i for i, c in enumerate(chunks) if isinstance(c, str))
    events = [c.get("event") for c in chunks[:first_text] if isinstance(c, dict)]
    assert "tool_usage" in events and "tool_response" in events
    assert "".join(texts(chunks)) == "".join(LONG)


@pytest.mark.asyncio
async def test_a_sub_agent_answer_streams_without_the_handoff_line(monkeypatch):
    saver = InMemorySaver()
    lead = Streaming(replies=[calls_tool("transfer_to_Search", "One moment.")])
    search = Streaming(replies=[text(*LONG)])
    serve(
        monkeypatch,
        make_agent(
            "Abi",
            lead,
            agents=[make_agent("Search", search, saver=saver)],
            saver=saver,
            supervised=True,
        ),
    )

    chunks = await chunks_of()

    assert len(texts(chunks)) > 3
    assert "".join(texts(chunks)) == "".join(LONG)


@pytest.mark.asyncio
async def test_a_client_that_leaves_stops_the_model(monkeypatch):
    model = Streaming(replies=[text(*(LONG * 4))], delay=0.02)
    serve(monkeypatch, make_agent("Abi", model))

    stream = stream_with_abi_inprocess(
        [Message(role="user", content="hello")],
        CONFIG,
        thread_id="conv-1",
        user_context_preamble=None,
    )
    async for chunk in stream:
        if isinstance(chunk, str):
            break
    await stream.aclose()

    for _ in range(250):
        if model.stopped_early:
            break
        await asyncio.sleep(0.02)
    assert model.stopped_early == [True]


class Echo(BaseChatModel):
    """Answers each turn about its own question, a few words at a time."""

    delay: float = 0.01

    @property
    def _llm_type(self) -> str:
        return "streaming-echo"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Echo:
        return self

    @staticmethod
    def _answer(messages) -> list[str]:
        question = str(messages[-1].content).strip()
        return [f"About {question}: " for _ in range(30)]

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        content = "".join(self._answer(messages))
        message = message_chunk_to_message(AIMessageChunk(content=content))
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        for piece in self._answer(messages):
            time.sleep(self.delay)
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece))


def turn(question: str):
    return stream_with_abi_inprocess(
        [Message(role="user", content=question)],
        CONFIG,
        thread_id="conv-voice",
        user_context_preamble=None,
    )


@pytest.mark.asyncio
async def test_after_a_barge_in_the_next_turn_carries_only_its_own_text(monkeypatch):
    # Voice barge-in: turn N is cut mid-answer, turn N+1 follows on the same
    # conversation thread and cached template. The str chunks are what the chat
    # streams as content and what it saves as the message.
    serve(monkeypatch, make_agent("Abi", Echo(delay=0.02)))

    first = turn("first")
    async for chunk in first:
        if isinstance(chunk, str):
            break
    await first.aclose()

    second = "".join(texts([chunk async for chunk in turn("second")]))

    assert second == "About second: " * 30


@pytest.mark.asyncio
async def test_overlapping_turns_on_one_thread_keep_their_own_text(monkeypatch):
    # Three transcripts of one utterance sent within half a second, none
    # cancelled: each stream still says only its own answer.
    serve(monkeypatch, make_agent("Abi", Echo()))

    async def said(question: str) -> str:
        return "".join(texts([chunk async for chunk in turn(question)]))

    answers = await asyncio.gather(said("one"), said("two"), said("three"))

    assert answers == [f"About {q}: " * 30 for q in ("one", "two", "three")]


@pytest.mark.asyncio
async def test_a_remote_agent_streams_its_deltas_once():
    class Directory:
        async def stream(self, model, prompt, *, thread_id, invocation_id):
            for event in (
                {"event": "tool_usage", "data": "search"},
                {"event": "ai_message_delta", "data": "Hello "},
                {"event": "ai_message_delta", "data": "world."},
                {"event": "ai_message", "data": "Hello world."},
                {"event": "message", "data": "Hello world."},
                {"event": "done", "data": "[DONE]"},
            ):
                yield event

    chunks = [
        chunk
        async for chunk in remote_agent_chunks(
            [Message(role="user", content="hi")],
            CONFIG,
            "conv-1",
            user_context_preamble=None,
            invocation_id=None,
            directory=Directory(),
        )
    ]

    assert texts(chunks) == ["Hello ", "world."]


def test_event_chunks_add_only_what_the_deltas_did_not_carry():
    to_chunk = AgentEventChunks()

    assert to_chunk("ai_message_delta", "Hello") == "Hello"
    assert to_chunk("ai_message_delta", " ") == " "
    assert to_chunk("ai_message", "Hello world") == "world"
    assert to_chunk("ai_message", "Whole second message") == "Whole second message"


def test_event_chunks_start_a_later_streamed_answer_on_a_new_paragraph():
    to_chunk = AgentEventChunks()

    assert to_chunk("ai_message_delta", "Let me look that up for you.") == (
        "Let me look that up for you."
    )
    assert to_chunk("tool_usage", "search") == {"event": "tool_usage", "tool": "search"}
    assert to_chunk("ai_message_delta", "Found it.") == "\n\nFound it."
    assert to_chunk("ai_message", "Found it.") is None
