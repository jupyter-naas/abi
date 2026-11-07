"""Real Agent and IntentAgent hosted behind SDK proxies over a native broker."""

import asyncio
from typing import TypedDict

import nats
import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from naas_abi_core.engine.nats_rpc_integration_test import SECRET, broker  # noqa: F401
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.agent.Agent import Agent
from naas_abi_core.services.agent.IntentAgent import IntentAgent
from naas_abi_core.services.agent.RemoteAgentAdapter import RemoteAgentAdapter
from naas_abi_core.services.discovery.discovery_factory import start_discovery
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterNATSClient_test import (
    document_host,  # noqa: F401
)
from naas_abi_sdk.credentials import host_audience

pytestmark = [
    pytest.mark.integration,
    pytest.mark.parametrize("broker", [8 * 1024 * 1024], indirect=True),
]


def _host_token(name):
    """What a module's call to another module's host carries: its token, addressed
    to that host."""
    return lambda recipient: TEST_TOKENS.token(name, audience=host_audience(recipient))


def test_core_agents_and_async_parent_tool_over_network(document_host):  # noqa: F811
    from naas_abi_proto.agent.v1 import agent_pb2 as pb
    from naas_abi_sdk import (
        AgentDescriptor,
        BaseModule,
        DiscoveryConfiguration,
        ModuleDependencies,
        run_module,
    )
    from naas_abi_sdk.agent import agent_subject
    from naas_abi_sdk.transport import RPCError, Transport

    async def scenario():
        nc = await nats.connect(document_host)
        registry = await start_discovery(nc, SECRET)
        stop = asyncio.Event()
        token = TEST_TOKENS.token("agent-test")

        class Provider(BaseModule):
            module_id = "test.agents"
            dependencies = ModuleDependencies(services=("document",))
            agents = tuple(
                AgentDescriptor(name, capabilities=("agent.invoke.v1",))
                for name in ("Simple", "Intent", "Large")
            )

            async def on_initialized(self):
                class LargeHandler:
                    async def invoke(self, prompt, context):
                        return "large-result-" * 12000

                    async def stream_invoke(self, prompt, context):
                        yield {"event": "call_model", "data": "history-" * 20000}
                        yield {"event": "message", "data": "large-result-" * 12000}

                self.expose_agent("Large", LargeHandler())

                kwargs = {
                    "description": "Test agent",
                    "chat_model": FakeListChatModel(responses=["network answer"]),
                    "memory": MemorySaver(),
                    "enable_default_tools": False,
                }
                self.expose_agent(
                    "Simple", RemoteAgentAdapter(Agent(name="Simple", **kwargs))
                )
                self.expose_agent(
                    "Intent",
                    RemoteAgentAdapter(
                        IntentAgent(
                            name="Intent",
                            embedding_model=DeterministicFakeEmbedding(size=8),
                            enable_default_intents=False,
                            **kwargs,
                        )
                    ),
                )

            async def run(self):
                await stop.wait()

        class Consumer(BaseModule):
            module_id = "test.caller"
            dependencies = ModuleDependencies(modules=("test.agents",))

            async def run(self):
                module = self.engine.modules["test.agents"]
                for name in ("Simple", "Intent"):
                    proxy = await module.get_agent(name)
                    assert await proxy.invoke("hello", timeout=10) == "network answer"
                    events = [
                        event
                        async for event in proxy.stream_invoke(
                            "hello again", timeout=10
                        )
                    ]
                    assert {"event": "message", "data": "network answer"} in events
                    assert events[-1] == {"event": "done", "data": "[DONE]"}
                large = await module.get_agent("Large")
                assert await large.invoke("hi", timeout=20) == "large-result-" * 12000
                large_events = [
                    event async for event in large.stream_invoke("hi", timeout=20)
                ]
                assert large_events[0]["data"] == "history-" * 20000
                assert large_events[1]["data"] == "large-result-" * 12000
                proxy = await module.get_agent("Simple")

                class State(TypedDict):
                    result: str

                async def parent(state):
                    return {
                        "result": await proxy.as_tools()[0].ainvoke(
                            {"prompt": "tool call"}
                        )
                    }

                builder = StateGraph(State)
                builder.add_node("remote", parent)
                builder.add_edge(START, "remote")
                builder.add_edge("remote", END)
                assert (await builder.compile().ainvoke({"result": ""}))[
                    "result"
                ] == "network answer"
                # Host validates the incoming token through the engine, not just discovery lookup.
                target = (await module.ready_instances())[0]
                bad = Transport(
                    document_host,
                    "invalid",
                    timeout=2,
                    host_token=lambda recipient: "invalid",
                )
                try:
                    with pytest.raises(RPCError, match="UNAUTHENTICATED"):
                        await bad.call(
                            agent_subject(
                                "default",
                                target.service_account,
                                target.instance_id,
                                "Simple",
                                "submit",
                            ),
                            pb.SubmitRequest(
                                invocation_id="invalid",
                                thread_id="thread",
                                prompt="hi",
                                mode="invoke",
                                deadline_seconds=5,
                            ),
                            pb.SubmitResponse,
                        )
                finally:
                    await bad.close()

        task = asyncio.create_task(
            run_module(
                Provider,
                url=document_host,
                token=token,
                host_token=_host_token("agent-test"),
                discovery=DiscoveryConfiguration(),
            )
        )
        try:
            await asyncio.wait_for(
                run_module(
                    Consumer,
                    url=document_host,
                    token=token,
                    host_token=_host_token("agent-test"),
                    discovery=DiscoveryConfiguration(refresh_seconds=0.05),
                ),
                30,
            )
        finally:
            stop.set()
            await task
            await registry.stop()
            await nc.close()

    asyncio.run(scenario())


def test_a_tool_that_opts_out_of_chat_sources_streams_over_the_network(document_host):  # noqa: F811
    """A core agent whose tool sets metadata {"chat_source": False} streams
    through RemoteAgentAdapter: the run completes, and the opt-out reaches the
    caller on the live stream and on the stored replay."""
    from langchain_core.messages import AIMessage
    from langchain_core.tools import tool
    from naas_abi_core.services.agent.Agent_stream_test import _ScriptedChatModel
    from naas_abi_sdk import (
        AgentDescriptor,
        BaseModule,
        DiscoveryConfiguration,
        ModuleDependencies,
        run_module,
    )

    @tool
    def lookup(term: str) -> str:
        """Look a term up.

        Args:
            term (str): The term.
        """
        return f"https://example.org/{term}"

    @tool
    def internal_lookup(term: str) -> str:
        """Look a term up in the internal index.

        Args:
            term (str): The term.
        """
        return f"https://internal.example.org/{term}"

    internal_lookup.metadata = {"chat_source": False}

    def tool_responses(events):
        return [
            {k: v for k, v in e.items() if k != "sequence"}
            for e in events
            if e["event"] == "tool_response"
        ]

    expected = [
        {"event": "tool_response", "data": "https://example.org/a"},
        {
            "event": "tool_response",
            "data": "https://internal.example.org/b",
            "chat_source": False,
        },
    ]

    async def scenario():
        nc = await nats.connect(document_host)
        registry = await start_discovery(nc, SECRET)
        stop = asyncio.Event()
        token = TEST_TOKENS.token("agent-test")

        class Provider(BaseModule):
            module_id = "test.sources"
            dependencies = ModuleDependencies(services=("document",))
            agents = (AgentDescriptor("Quiet", capabilities=("agent.invoke.v1",)),)

            async def on_initialized(self):
                def turn(n):
                    return [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "lookup",
                                    "args": {"term": "a"},
                                    "id": f"a{n}",
                                },
                                {
                                    "name": "internal_lookup",
                                    "args": {"term": "b"},
                                    "id": f"b{n}",
                                },
                            ],
                        ),
                        AIMessage(content="done"),
                    ]

                # One scripted model for every run's duplicate: two turns of
                # one conversation, with their own tool call ids.
                model = _ScriptedChatModel(script=turn(1) + turn(2))
                agent = Agent(
                    name="Quiet",
                    description="Test agent",
                    chat_model=model,
                    tools=[lookup, internal_lookup],
                    memory=MemorySaver(),
                    enable_default_tools=False,
                )
                self.expose_agent("Quiet", RemoteAgentAdapter(agent))

            async def run(self):
                await stop.wait()

        class Consumer(BaseModule):
            module_id = "test.reader"
            dependencies = ModuleDependencies(modules=("test.sources",))

            async def run(self):
                proxy = await self.engine.modules["test.sources"].get_agent("Quiet")
                events = [e async for e in proxy.stream_invoke("look", timeout=20)]
                assert tool_responses(events) == expected
                assert events[-1] == {"event": "done", "data": "[DONE]"}

                handle = await proxy.submit("look again", stream=True)
                assert tool_responses([e async for e in handle.events(timeout=20)]) == (
                    expected
                )
                status = await handle.status()
                assert status.status == "SUCCEEDED"
                assert tool_responses(status.events) == expected

        task = asyncio.create_task(
            run_module(
                Provider,
                url=document_host,
                token=token,
                host_token=_host_token("agent-test"),
                discovery=DiscoveryConfiguration(),
            )
        )
        try:
            await asyncio.wait_for(
                run_module(
                    Consumer,
                    url=document_host,
                    token=token,
                    host_token=_host_token("agent-test"),
                    discovery=DiscoveryConfiguration(refresh_seconds=0.05),
                ),
                40,
            )
        finally:
            stop.set()
            await task
            await registry.stop()
            await nc.close()

    asyncio.run(scenario())


def test_a_run_stays_reachable_after_its_owner_loses_the_lease(document_host):  # noqa: F811
    from naas_abi_sdk import (
        AgentDescriptor,
        BaseModule,
        DiscoveryConfiguration,
        ModuleDependencies,
        run_module,
    )
    from naas_abi_sdk.discovery import DiscoveryClient
    from naas_abi_sdk.transport import RPCError, Transport

    async def scenario():
        nc = await nats.connect(document_host)
        # A 2 s lease: the provider renews every half second.
        registry = await start_discovery(nc, SECRET, lease_seconds=2)
        stop = asyncio.Event()
        token = TEST_TOKENS.token("agent-test")
        admin_transport = Transport(document_host, TEST_TOKENS.token("api"), timeout=2)
        admin = DiscoveryClient(admin_transport)

        class Provider(BaseModule):
            module_id = "test.lease"
            dependencies = ModuleDependencies(services=("document",))
            agents = (AgentDescriptor("Long", capabilities=("agent.invoke.v1",)),)

            async def on_initialized(self):
                class Long:
                    async def invoke(self, prompt, context):
                        raise AssertionError("streamed only")

                    async def stream_invoke(self, prompt, context):
                        yield {"event": "message", "data": "started"}
                        await asyncio.Event().wait()  # until cancelled

                self.expose_agent("Long", Long())

            async def run(self):
                await stop.wait()

        class Consumer(BaseModule):
            module_id = "test.lease-caller"
            dependencies = ModuleDependencies(modules=("test.lease",))

            async def run(self):
                module = self.engine.modules["test.lease"]
                proxy = await module.get_agent("Long")
                handle = await proxy.submit("go", stream=True, deadline_seconds=60)
                events = handle.events(timeout=30)
                assert (await events.__anext__())["data"] == "started"
                owner = handle.owner_instance_id

                # Discovery drops the owner's registration mid-run.
                assert (await admin.evict(owner)).instance_id == owner

                async def registered_again():
                    while True:
                        try:
                            return await module.ready_instances()
                        except RPCError as exc:
                            if exc.code not in (
                                "MODULE_NOT_FOUND",
                                "MODULE_UNAVAILABLE",
                            ):
                                raise
                        await asyncio.sleep(0.05)

                ready = await asyncio.wait_for(registered_again(), 10)

                status = await handle.status()
                assert (status.status, status.owner_instance_id) == ("RUNNING", owner)
                assert status.owner_available
                # The same process, under the same instance id.
                assert [i.instance_id for i in ready] == [owner]
                # The live run still holds its conversation.
                busy = await (await proxy.submit("again", stream=True)).status()
                assert (busy.status, busy.error_code) == ("FAILED", "CONVERSATION_BUSY")
                assert (await handle.status()).status == "RUNNING"

                # Any handle can stop it, and the watching one sees the end.
                await proxy.invocation(handle.invocation_id).cancel()
                with pytest.raises(RPCError, match="CANCELLED"):
                    async for _ in events:
                        pass

        task = asyncio.create_task(
            run_module(
                Provider,
                url=document_host,
                token=token,
                host_token=_host_token("agent-test"),
                discovery=DiscoveryConfiguration(),
            )
        )
        try:
            await asyncio.wait_for(
                run_module(
                    Consumer,
                    url=document_host,
                    token=token,
                    host_token=_host_token("agent-test"),
                    discovery=DiscoveryConfiguration(refresh_seconds=0.05),
                ),
                30,
            )
        finally:
            stop.set()
            await task
            await admin_transport.close()
            await registry.stop()
            await nc.close()

    asyncio.run(scenario())
