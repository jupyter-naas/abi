import asyncio

import pytest

pytest.importorskip("langgraph.graph")

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from naas_abi_sdk.agent_host import InvocationContext
from naas_abi_sdk.agents import Agent, AgentConfiguration
from naas_abi_sdk.agents.hosting import agent_memory_id, document_memory


class _EchoModel(BaseChatModel):
    """Answers with how many human messages it can see (i.e. the thread history)."""

    seen: list[int] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "echo"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        humans = [m for m in messages if m.type == "human"]
        self.seen.append(len(humans))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(f"turn {len(humans)}"))]
        )


def _agent(model):
    return Agent(
        "Echo",
        "Echoes the turn count.",
        model,
        configuration=AgentConfiguration(system_prompt="echo"),
    )


def _context(thread_id):
    return InvocationContext("inv", thread_id, "caller")


def test_handler_runs_each_invocation_on_the_context_thread():
    model = _EchoModel()
    handler = _agent(model).as_handler()

    async def run():
        assert await handler.invoke("a", _context("conv-1")) == "turn 1"
        assert await handler.invoke("b", _context("conv-1")) == "turn 2"
        assert await handler.invoke("c", _context("conv-2")) == "turn 1"

    asyncio.run(run())


def test_handler_streams_core_events():
    handler = _agent(_EchoModel()).as_handler()

    async def run():
        return [event async for event in handler.stream_invoke("hi", _context("t"))]

    assert asyncio.run(run()) == [
        {"event": "call_model", "data": "Echo"},
        {"event": "ai_message", "data": "turn 1"},
        {"event": "message", "data": "turn 1"},
        {"event": "done", "data": "[DONE]"},
    ]


def test_handler_stops_streaming_once_cancelled():
    handler = _agent(_EchoModel()).as_handler()
    context = _context("t")

    async def run():
        events = []
        async for event in handler.stream_invoke("hi", context):
            events.append(event)
            context.cancelled.set()
        return events

    assert len(asyncio.run(run())) == 1


def test_handler_is_accepted_by_expose_agent():
    from naas_abi_sdk.discovery import AgentDescriptor
    from naas_abi_sdk.module import BaseModule

    class _Module(BaseModule):
        agents = (AgentDescriptor("Echo", capabilities=("agent.invoke.v1",)),)

    module = object.__new__(_Module)
    module._agent_handlers = {}
    module.expose_agent("Echo", _agent(_EchoModel()).as_handler())

    assert "Echo" in module._agent_handlers


def test_document_memory_sets_up_the_checkpoint_collections():
    created = []

    class _Documents:
        async def ensure_collection(self, request):
            created.append(request.spec.name)

    saver = asyncio.run(
        document_memory(_Documents(), agent_memory_id("acme.research", "Researcher"))
    )

    assert type(saver).__name__ == "DocumentCheckpointSaver"
    assert saver.agent_id == "acme.research.Researcher.v1"
    assert created == ["langgraph_checkpoints_v1", "langgraph_writes_v1"]
