"""A remote agent run's events are pushed to the caller, not polled, over a native broker."""

import asyncio

import nats
import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_rpc_integration_test import SECRET, broker  # noqa: F401
from naas_abi_core.services.discovery.discovery_factory import start_discovery
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterNATSClient_test import (
    document_host,  # noqa: F401
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.parametrize("broker", [8 * 1024 * 1024], indirect=True),
]

LARGE = "large-event-" * 5000  # above the inline bound: read in parts


def test_run_events_are_pushed_and_status_is_read_once(document_host):  # noqa: F811
    from naas_abi_sdk import (
        AgentDescriptor,
        BaseModule,
        DiscoveryConfiguration,
        ModuleDependencies,
        run_module,
    )

    async def scenario():
        nc = await nats.connect(document_host)
        registry = await start_discovery(nc, SECRET)
        stop = asyncio.Event()
        token = issue_service_token("agent-updates-test", SECRET)
        # Every agent request crossing the broker, by operation.
        requests: dict[str, int] = {}

        async def observe(msg):
            operation = msg.subject.rsplit(".", 1)[1]
            requests[operation] = requests.get(operation, 0) + 1

        await nc.subscribe("abi.agent.>", cb=observe)
        await nc.flush()

        class Provider(BaseModule):
            module_id = "test.slow"
            dependencies = ModuleDependencies(services=("document",))
            agents = (AgentDescriptor("Slow", capabilities=("agent.invoke.v1",)),)

            async def on_initialized(self):
                class Slow:
                    async def invoke(self, prompt, context):
                        await asyncio.sleep(1.0)
                        return "slow answer"

                    async def stream_invoke(self, prompt, context):
                        yield {"event": "call_model", "data": "thinking"}
                        await asyncio.sleep(1.0)
                        yield {"event": "tool", "data": LARGE}
                        await asyncio.sleep(1.0)
                        yield {"event": "message", "data": "slow answer"}

                self.expose_agent("Slow", Slow())

            async def run(self):
                await stop.wait()

        class Consumer(BaseModule):
            module_id = "test.caller"
            dependencies = ModuleDependencies(modules=("test.slow",))

            async def run(self):
                proxy = await self.engine.modules["test.slow"].get_agent("Slow")

                requests.clear()
                events = [e async for e in proxy.stream_invoke("hi", timeout=30)]
                await nc.flush()
                assert events == [
                    {"event": "call_model", "data": "thinking"},
                    {"event": "tool", "data": LARGE},
                    {"event": "message", "data": "slow answer"},
                    {"event": "done", "data": "[DONE]"},
                ]
                # A 2 s run: polling read Status about 20 times. Pushed, it is
                # read once, for the authoritative end.
                assert requests.get("status", 0) == 1, requests
                assert requests.get("submit") == 1
                assert requests.get("event", 0) >= 1  # the large event's parts

                requests.clear()
                assert await proxy.invoke("hi", timeout=30) == "slow answer"
                await nc.flush()
                assert requests.get("status", 0) == 1, requests

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
                60,
            )
        finally:
            stop.set()
            await task
            await registry.stop()
            await nc.close()

    asyncio.run(scenario())
