import asyncio

import nats
import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_rpc_integration_test import SECRET, broker  # noqa: F401
from naas_abi_core.services.discovery.discovery_factory import start_discovery
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

pytestmark = [
    pytest.mark.integration,
    pytest.mark.parametrize("broker", [8 * 1024 * 1024], indirect=True),
]


def test_registry_auth_expiry_restart_and_sdk_dependency_runner(broker):  # noqa: F811
    sdk = pytest.importorskip("naas_abi_sdk")
    discovery = pytest.importorskip("naas_abi_sdk.discovery")
    transport_module = pytest.importorskip("naas_abi_sdk.transport")
    BaseModule, ModuleDependencies, run_module = (
        sdk.BaseModule,
        sdk.ModuleDependencies,
        sdk.run_module,
    )
    AgentDescriptor, DiscoveryClient, DiscoveryConfiguration = (
        discovery.AgentDescriptor,
        discovery.DiscoveryClient,
        discovery.DiscoveryConfiguration,
    )
    RPCError, Transport = transport_module.RPCError, transport_module.Transport

    async def scenario():
        url, _ = broker
        nc = await nats.connect(url)
        primary = await start_discovery(nc, SECRET, lease_seconds=1)
        transport = Transport(url, issue_service_token("test", SECRET), timeout=0.5)
        client = DiscoveryClient(transport)
        provider_started, stop = asyncio.Event(), asyncio.Event()
        provider_task = None

        class Provider(BaseModule):
            module_id = "research"
            agents = (AgentDescriptor("Researcher", "Find facts"),)

            async def run(self):
                provider_started.set()
                await stop.wait()

        class Consumer(BaseModule):
            module_id = "consumer"
            dependencies = ModuleDependencies(modules=("research",))

            async def run(self):
                proxy = self.engine.modules["research"]
                assert (await proxy.list_agents())[0].name == "Researcher"
                with pytest.raises(ValueError, match="did not declare"):
                    self.engine.modules["other"]
                return True

        try:
            bad = DiscoveryClient(Transport(url, "invalid", timeout=0.5))
            try:
                with pytest.raises(RPCError, match="UNAUTHENTICATED"):
                    await bad.list_modules()
            finally:
                await bad.transport.close()
            config = DiscoveryConfiguration(startup_timeout=3, refresh_seconds=0.05)
            consumer = asyncio.create_task(
                run_module(
                    Consumer,
                    url=url,
                    token=transport.token,
                    timeout=0.5,
                    discovery=config,
                )
            )
            await asyncio.sleep(0.1)
            assert not consumer.done()
            provider_task = asyncio.create_task(
                run_module(
                    Provider,
                    url=url,
                    token=transport.token,
                    timeout=0.5,
                    discovery=config,
                )
            )
            await asyncio.wait_for(provider_started.wait(), 3)
            assert await consumer
            # An owner restart recovers registrations from JetStream.
            await primary.stop()
            primary = await start_discovery(nc, SECRET, lease_seconds=1)
            assert (await client.get_module("research"))[0].status == "READY"
            initial_id = (await client.get_module("research"))[0].instance_id
            await primary.stop()
            await asyncio.sleep(1.1)
            primary = await start_discovery(nc, SECRET, lease_seconds=1)

            async def wait_recovery():
                while True:
                    try:
                        instances = await client.get_module("research")
                        if (
                            instances[0].status == "READY"
                            and instances[0].instance_id != initial_id
                        ):
                            return
                    except RPCError as exc:
                        if exc.code != "MODULE_NOT_FOUND":
                            raise
                    await asyncio.sleep(0.05)

            await asyncio.wait_for(wait_recovery(), 5)
            stop.set()
            await provider_task
            with pytest.raises(RPCError, match="MODULE_NOT_FOUND"):
                await client.get_module("research")
            req = pb.RegisterRequest(
                descriptor=pb.ModuleDescriptor(module_id="orphan", contract_major=1),
                instance_id="orphan",
                lease_token="x" * 32,
            )
            await client._call("register", req, pb.RegisterResponse)
            await asyncio.sleep(1.1)
            with pytest.raises(RPCError, match="MODULE_NOT_FOUND"):
                await client.get_module("orphan")
        finally:
            stop.set()
            if provider_task:
                await provider_task
            await transport.close()
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())


def test_two_registry_owners_do_not_duplicate_mutations(broker):  # noqa: F811
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from naas_abi_sdk.transport import Transport

    async def scenario():
        nc = await nats.connect(broker[0])
        primaries = [await start_discovery(nc, SECRET) for _ in range(2)]
        for primary in primaries:
            primary.service.register = AsyncMock(wraps=primary.service.register)
        transport = Transport(broker[0], issue_service_token("test", SECRET))
        try:
            for _ in range(4):
                await transport.call(
                    "abi.discovery.default.v1.register",
                    pb.RegisterRequest(
                        descriptor=pb.ModuleDescriptor(
                            module_id="replicated", contract_major=1
                        ),
                        instance_id=str(uuid4()),
                        lease_token=uuid4().hex,
                    ),
                    pb.RegisterResponse,
                )
            await nc.flush()
            assert sum(p.service.register.await_count for p in primaries) == 4
            result = await transport.call(
                "abi.discovery.default.v1.get_module",
                pb.GetModuleRequest(module_id="replicated", contract_major=1),
                pb.GetModuleResponse,
            )
            assert len(result.instances) == 4
        finally:
            await transport.close()
            for primary in primaries:
                await primary.stop()
            await nc.close()

    asyncio.run(scenario())
