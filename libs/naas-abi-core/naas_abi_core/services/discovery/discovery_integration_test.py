import asyncio

import nats
import pytest
from naas_abi_core.engine.nats_rpc_integration_test import SECRET, broker  # noqa: F401
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
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
        transport = Transport(url, TEST_TOKENS.token("test"), timeout=0.5)
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
                        if instances[0].status == "READY":
                            return instances
                    except RPCError as exc:
                        if exc.code != "MODULE_NOT_FOUND":
                            raise
                    await asyncio.sleep(0.05)

            # The lease expired while discovery was down: the provider
            # registered again under its instance id, with a fresh lease.
            recovered = await asyncio.wait_for(wait_recovery(), 5)
            assert [i.instance_id for i in recovered] == [initial_id]
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
        transport = Transport(broker[0], TEST_TOKENS.token("test"))
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


def test_admins_evict_a_live_instance_which_registers_again(broker):  # noqa: F811
    """Evicting is discovery:Evict, a policy: api holds it, a module whose
    policy covers only its own registration does not."""
    discovery = pytest.importorskip("naas_abi_sdk.discovery")
    transport_module = pytest.importorskip("naas_abi_sdk.transport")
    from naas_abi_core.services.iam.tests.authorization_contract import (
        contract_iam,
    )
    from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement

    iam = contract_iam()
    harness = IAMHarness(iam)
    research = harness.service_account("research")
    harness.grant(
        research.id,
        statement(
            "Allow",
            [
                "discovery:Register",
                "discovery:Renew",
                "discovery:Unregister",
                "discovery:GetModule",
                "discovery:ListModules",
            ],
            ["abi:discovery:module/evict/research"],
        ),
    )

    async def scenario():
        url, _ = broker
        nc = await nats.connect(url)
        primary = await start_discovery(
            nc, SECRET, project="evict", lease_seconds=2, iam=iam
        )
        module = transport_module.Transport(
            url, TEST_TOKENS.token("research"), timeout=2
        )
        admin = transport_module.Transport(url, TEST_TOKENS.token("api"), timeout=2)
        session = discovery.DiscoverySession(
            discovery.DiscoveryClient(module, "evict"),
            pb.ModuleDescriptor(module_id="research", contract_major=1),
        )
        try:
            await session.start()
            first, lease_token = session.instance_id, session.lease_token
            client = discovery.DiscoveryClient(admin, "evict")

            with pytest.raises(transport_module.RPCError, match="PERMISSION_DENIED"):
                await discovery.DiscoveryClient(module, "evict").evict(first)
            evicted = await client.evict(first)
            assert (evicted.module_id, evicted.instance_id) == ("research", first)

            # The heartbeat (at most a quarter lease) sees LEASE_EXPIRED and
            # registers again, under the same instance id with a fresh lease.
            for _ in range(60):
                instances, _ = await client.list_modules()
                if instances:
                    break
                await asyncio.sleep(0.1)
            assert [i.instance_id for i in instances] == [first]
            assert session.instance_id == first
            assert session.lease_token != lease_token
        finally:
            await session.close()
            await module.close()
            await admin.close()
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())


def test_concurrent_registrations_through_two_owners_all_succeed(broker):  # noqa: F811
    from uuid import uuid4

    from naas_abi_sdk.transport import Transport

    async def scenario():
        nc = await nats.connect(broker[0])
        primaries = [await start_discovery(nc, SECRET) for _ in range(2)]
        transport = Transport(broker[0], TEST_TOKENS.token("test"))
        try:
            responses = await asyncio.gather(
                *(
                    transport.call(
                        "abi.discovery.default.v1.register",
                        pb.RegisterRequest(
                            descriptor=pb.ModuleDescriptor(
                                module_id="crowd", contract_major=1
                            ),
                            instance_id=str(uuid4()),
                            lease_token=uuid4().hex,
                        ),
                        pb.RegisterResponse,
                    )
                    for _ in range(40)
                )
            )
            result = await transport.call(
                "abi.discovery.default.v1.get_module",
                pb.GetModuleRequest(module_id="crowd", contract_major=1),
                pb.GetModuleResponse,
            )
        finally:
            await transport.close()
            for primary in primaries:
                await primary.stop()
            await nc.close()
        return responses, result

    responses, result = asyncio.run(scenario())

    # Each owner batches the calls it receives; their writes race on one KV key.
    assert [r.error.code for r in responses if r.error.code] == []
    assert len(result.instances) == 40
