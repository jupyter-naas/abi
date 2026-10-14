"""Actual Agent/IntentAgent and SDK model proxies over a native NATS broker."""

import asyncio

import nats
import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_rpc_integration_test import SECRET, broker  # noqa: F401
from naas_abi_core.models.Model import ChatModel, EmbeddingModel
from naas_abi_core.services.agent.Agent import Agent, AgentSharedState
from naas_abi_core.services.agent.IntentAgent import IntentAgent
from naas_abi_core.services.model_registry.adapters.primary.model_registry_nats import (
    ModelRegistryNATS,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb
from naas_abi_sdk import ABIClient, BaseModule, ModuleDependencies, run_module
from naas_abi_sdk.services.model_registry import ModelRegistryService as RegistryFacade
from naas_abi_sdk.transport import RPCError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.parametrize("broker", [8 * 1024 * 1024], indirect=True),
]


class ToolModel(FakeListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=tools, **kwargs)

    def _generate(self, messages, **kwargs):
        if isinstance(messages[-1], ToolMessage):
            message = AIMessage(content=f"Result: {messages[-1].content}")
        else:
            assert kwargs["tools"][0]["function"]["name"] == "add"
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "add",
                        "args": {"a": 2, "b": 3},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        for chunk in self._stream(messages, stop, **kwargs):
            yield chunk

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        result = self._generate(messages, **kwargs).generations[0].message
        if result.tool_calls:
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {"name": "add", "args": '{"a":2,', "id": "call-1", "index": 0}
                    ],
                )
            )
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {"name": None, "args": '"b":3}', "id": None, "index": 0}
                    ],
                )
            )
        else:
            yield ChatGenerationChunk(message=AIMessageChunk(content=result.content))


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def test_models_and_real_agents(broker):  # noqa: F811
    url = broker[0]

    async def scenario():
        owner = ModelRegistryService(
            default_chat_model="chat", default_embedding_model="embedding"
        )
        owner.register(
            "chat",
            ChatModel(
                model_id="fake",
                provider="test",
                model=FakeListChatModel(responses=["network answer"]),
            ),
        )
        owner.register(
            "tools",
            ChatModel(
                model_id="tools", provider="test", model=ToolModel(responses=["unused"])
            ),
        )
        owner.register(
            "embedding",
            EmbeddingModel(
                model_id="embed",
                provider="test",
                model=DeterministicFakeEmbedding(size=8),
            ),
        )
        nc = await nats.connect(url)
        primary = ModelRegistryNATS(owner, SECRET, stream_ttl=0.2)
        await primary.start(nc)
        token = issue_service_token("model-test", SECRET)

        class Consumer(BaseModule):
            dependencies = ModuleDependencies(services=("model_registry",))

            async def run(self):
                registry = self.engine.services.model_registry
                assert set(await registry.list_canonical_ids()) == {
                    "chat",
                    "tools",
                    "embedding",
                }
                chat = (await registry.get_default_chat_model()).model
                embedding = (await registry.get_default_embedding_model()).model
                assert (await chat.ainvoke("hello")).content == "network answer"
                assert (
                    "".join([c.content async for c in chat.astream("stream")])
                    == "network answer"
                )
                assert len(await embedding.aembed_query("hello")) == 8
                assert len(await embedding.aembed_documents(["a", "b"])) == 2
                for cls in (Agent, IntentAgent):
                    kwargs = {
                        "name": cls.__name__,
                        "description": "Remote model test",
                        "chat_model": chat,
                        "memory": MemorySaver(),
                        "state": AgentSharedState(),
                        "enable_default_tools": False,
                    }
                    if cls is IntentAgent:
                        kwargs.update(
                            embedding_model=embedding, enable_default_intents=False
                        )
                    agent = await asyncio.to_thread(cls, **kwargs)
                    assert (
                        await asyncio.to_thread(agent.invoke, "hello")
                        == "network answer"
                    )
                    events = await asyncio.to_thread(
                        lambda agent=agent: list(agent.stream_invoke("again"))
                    )
                    assert {"event": "message", "data": "network answer"} in events
                tools = (await registry.get_chat_model("tools")).model
                result = await tools.bind_tools([add]).ainvoke("add")
                assert result.tool_calls[0]["args"] == {"a": 2, "b": 3}
                from pydantic import create_model

                schema = create_model("add", a=(int, ...), b=(int, ...))
                parsed = await tools.with_structured_output(schema).ainvoke("add")
                assert (parsed.a, parsed.b) == (2, 3)
                chunks = [c async for c in tools.bind_tools([add]).astream("add")]
                merged = chunks[0]
                for chunk in chunks[1:]:
                    merged += chunk
                assert merged.tool_calls[0]["args"] == {"a": 2, "b": 3}
                agent = Agent(
                    name="Calculator",
                    description="Add",
                    chat_model=tools,
                    tools=[add],
                    memory=MemorySaver(),
                    state=AgentSharedState(),
                    enable_default_tools=False,
                )
                assert "5" in await asyncio.to_thread(agent.invoke, "add 2 and 3")
                with pytest.raises(RPCError, match="MODEL_NOT_FOUND"):
                    await registry.get_chat_model("absent")

        try:
            await asyncio.wait_for(run_module(Consumer, url=url, token=token), 45)
            async with ABIClient(url, "invalid") as client:
                with pytest.raises(RPCError, match="UNAUTHENTICATED"):
                    await client.model_registry.list_models(pb.ListModelsRequest())
            async with (
                ABIClient(url, token) as client,
                ABIClient(url, issue_service_token("other", SECRET)) as other,
            ):
                request = pb.StreamOpenRequest(
                    chat=pb.ChatRequest(
                        ref=pb.ModelRef(canonical_id="chat", kind="chat"),
                        messages=[
                            pb.ChatMessage(type="human", data_json=b'{"content":"hi"}')
                        ],
                    )
                )
                opened = await client.model_registry.stream_open(request)
                with pytest.raises(RPCError, match="PERMISSION_DENIED"):
                    await other.model_registry.stream_close(
                        pb.StreamCloseRequest(stream_id=opened.stream_id)
                    )
                await asyncio.sleep(0.5)
                assert not primary.streams
                facade = RegistryFacade(client.model_registry)
                model = (await facade.get_chat_model("chat")).model
                with pytest.raises(RPCError, match="INVALID_ARGUMENT"):
                    await model.ainvoke("hi", api_key="forbidden")
        finally:
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())


def test_stream_deadlines_cleanup_and_provider_errors(broker):  # noqa: F811
    from langchain_core.messages import HumanMessage
    from naas_abi_sdk.model_codec import encode_message

    async def scenario():
        closed = asyncio.Event()

        class SlowModel(FakeListChatModel):
            async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
                try:
                    yield ChatGenerationChunk(message=AIMessageChunk(content="first"))
                    await asyncio.sleep(10)
                finally:
                    closed.set()

            async def _agenerate(self, messages, **kwargs):
                raise RuntimeError("sensitive-provider-credential")

        registry = ModelRegistryService()
        registry.register(
            "slow",
            ChatModel(
                model_id="slow", provider="test", model=SlowModel(responses=["unused"])
            ),
        )
        nc = await nats.connect(broker[0])
        host = ModelRegistryNATS(registry, SECRET, deadline=0.1)
        await host.start(nc)
        try:
            async with ABIClient(
                broker[0], issue_service_token("caller", SECRET), timeout=2
            ) as client:
                facade = RegistryFacade(client.model_registry)
                model = (await facade.get_chat_model("slow")).model
                with pytest.raises(RPCError, match="MODEL_ERROR") as exc:
                    await model.ainvoke("hi")
                assert "sensitive" not in str(exc.value)
                stream = model._astream([HumanMessage(content="hi")])
                assert (await stream.__anext__()).text == "first"
                await stream.aclose()
                await asyncio.wait_for(closed.wait(), 1)
                assert not host.streams
                closed.clear()
                stream = model._astream([HumanMessage(content="hi")])
                assert (await stream.__anext__()).text == "first"
                with pytest.raises(RPCError, match="DEADLINE_EXCEEDED"):
                    await stream.__anext__()
                assert closed.is_set()
                assert not host.streams
                # The server rejects an out-of-order cursor rather than silently
                # skipping or replaying an inference chunk.
                opened = await client.model_registry.stream_open(
                    pb.StreamOpenRequest(
                        chat=pb.ChatRequest(
                            ref=pb.ModelRef(canonical_id="slow", kind="chat"),
                            messages=[encode_message(HumanMessage(content="hi"))],
                        )
                    )
                )
                with pytest.raises(RPCError, match="INVALID_ARGUMENT"):
                    await client.model_registry.stream_next(
                        pb.StreamNextRequest(stream_id=opened.stream_id, sequence=9)
                    )
                await client.model_registry.stream_close(
                    pb.StreamCloseRequest(stream_id=opened.stream_id)
                )
        finally:
            await host.stop()
            await nc.close()

    asyncio.run(scenario())


def test_core_registry_returns_proxies_and_keeps_registration_local(broker):  # noqa: F811
    from naas_abi_core.engine import nats_runtime
    from naas_abi_core.services.model_registry.adapters.secondary.model_registry_client import (
        ModelRegistryNATSClient,
    )
    from naas_abi_sdk.models import ChatModelProxy

    async def scenario():
        owner = ModelRegistryService(default_chat_model="chat")
        nc = await nats.connect(broker[0])
        host = ModelRegistryNATS(owner, SECRET)
        await host.start(nc)
        client = ModelRegistryNATSClient(owner, broker[0], SECRET)
        try:
            client.register(
                "chat",
                ChatModel(
                    model_id="chat",
                    provider="test",
                    model=FakeListChatModel(responses=["core network answer"]),
                ),
            )
            model = await asyncio.to_thread(client.get_default_chat_model)
            assert isinstance(model, ChatModel)
            assert isinstance(model.model, ChatModelProxy)
            assert (
                await asyncio.to_thread(model.model.invoke, "hi")
            ).content == "core network answer"
            assert (await model.model.ainvoke("hi")).content == "core network answer"
            assert await asyncio.to_thread(client.list_canonical_ids) == ["chat"]
            client.register(
                "chat",
                ChatModel(
                    model_id="variant",
                    provider="test",
                    model=FakeListChatModel(responses=["variant answer"]),
                ),
            )
            variants = await asyncio.to_thread(client.list_models)
            assert (await variants[1].model.ainvoke("hi")).content == "variant answer"
        finally:
            await asyncio.to_thread(client.close)
            await asyncio.to_thread(nats_runtime.close)
            await host.stop()
            await nc.close()

    asyncio.run(scenario())
