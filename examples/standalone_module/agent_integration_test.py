"""Real Agent and IntentAgent hosted behind SDK proxies over a native broker."""

import asyncio
from typing import TypedDict

import nats
import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_rpc_integration_test import SECRET, broker  # noqa: F401
from naas_abi_core.services.agent.Agent import Agent
from naas_abi_core.services.agent.IntentAgent import IntentAgent
from naas_abi_core.services.agent.RemoteAgentAdapter import RemoteAgentAdapter
from naas_abi_core.services.discovery.discovery_factory import start_discovery
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterNATSClient_test import (
    document_host,  # noqa: F401
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.parametrize("broker", [8 * 1024 * 1024], indirect=True),
]


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
        token = issue_service_token("agent-test", SECRET)

        class Provider(BaseModule):
            module_id = "test.agents"
            dependencies = ModuleDependencies(services=("document",))
            agents = tuple(
                AgentDescriptor(name, capabilities=("agent.invoke.v1",))
                for name in ("Simple", "Intent")
            )

            async def on_initialized(self):
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
                bad = Transport(document_host, "invalid", timeout=2)
                try:
                    with pytest.raises(RPCError, match="UNAUTHENTICATED"):
                        await bad.call(
                            agent_subject(
                                "default", target.instance_id, "Simple", "submit"
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
                discovery=DiscoveryConfiguration(),
            )
        )
        try:
            await asyncio.wait_for(
                run_module(
                    Consumer,
                    url=document_host,
                    token=token,
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
