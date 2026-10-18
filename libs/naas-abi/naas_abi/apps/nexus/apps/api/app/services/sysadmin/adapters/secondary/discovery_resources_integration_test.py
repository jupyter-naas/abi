"""DiscoveryResources against a real nats-server running core discovery."""

import asyncio
import shutil
import subprocess
from uuid import uuid4

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.bus_resources_integration_test import (
    Broker,
    OnLoop,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.discovery_resources import (
    DiscoveryResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_integration_test import (
    _port,
    _wait_for,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS

pytestmark = pytest.mark.integration

SECRET = TEST_TOKENS.verifier


@pytest.fixture(scope="module")
def broker(tmp_path_factory):
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("nats-server is not installed")
    port = _port()
    process = subprocess.Popen(
        [
            binary,
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
            "-js",
            "-sd",
            str(tmp_path_factory.mktemp("js")),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(port)
        broker = Broker(f"nats://127.0.0.1:{port}")

        async def connect():
            import nats

            return await nats.connect(broker.url)

        broker.nc = broker.run(connect())
        yield broker
        broker.run(broker.nc.close())
        broker.loop.close()
    finally:
        process.terminate()
        process.wait(timeout=5)


async def _register(nc, project, module_id, instance_id, version, principal=None):
    """``principal``: the module's account when IAM decides, else its id."""
    from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

    request = pb.RegisterRequest(
        descriptor=pb.ModuleDescriptor(
            module_id=module_id,
            contract_major=1,
            package_version=version,
            agents=[pb.AgentDescriptor(name="Researcher", contract_major=1)],
        ),
        instance_id=instance_id,
        lease_token=uuid4().hex,
    )
    reply = await nc.request(
        f"abi.discovery.{project}.v1.register",
        request.SerializeToString(),
        timeout=5,
        headers={"Nats-Auth-Token": TEST_TOKENS.token(principal or module_id)},
    )
    assert not pb.RegisterResponse.FromString(reply.data).error.code


class Registry:
    """One fresh discovery project per test, seeded as the contract describes."""

    def __init__(self, broker, identity="api", iam=None):
        self.broker, self.identity, self.iam = broker, identity, iam
        self.project = f"p{uuid4().hex[:12]}"
        self.transports = []

    async def start(self):
        from naas_abi_core.services.discovery.discovery_factory import start_discovery

        self.primary = await start_discovery(
            self.broker.nc, SECRET, self.project, lease_seconds=300, iam=self.iam
        )
        # With IAM, a module registers as its own account (its bootstrap).
        accounts = {}
        if self.iam is not None:
            from naas_abi_core.services.iam.tests.iam_harness import IAMHarness

            harness = IAMHarness(self.iam)
            for module_id in ("acme", "zeta"):
                name = f"module/{self.project}/{module_id}"
                accounts[module_id] = harness.service_account(name).id
        for name, value in fixtures.SEED_ITEMS.items():
            await _register(
                self.broker.nc,
                self.project,
                "acme",
                name,
                value.decode(),
                accounts.get("acme"),
            )
        await _register(self.broker.nc, self.project, "zeta", "z-1", "1.0.0", accounts.get("zeta"))

    def client(self):
        from naas_abi_sdk.discovery import DiscoveryClient
        from naas_abi_sdk.transport import Transport

        transport = Transport(self.broker.url, lambda: TEST_TOKENS.token(self.identity), timeout=5)
        self.transports.append(transport)
        return DiscoveryClient(transport, self.project)

    async def stop(self):
        for transport in self.transports:
            await transport.close()
        await self.primary.stop()


@pytest.fixture
def registry(broker):
    registry = Registry(broker)
    broker.run(registry.start())
    yield registry
    broker.run(registry.stop())


@pytest.fixture
def discovery(broker, registry):
    return OnLoop(broker, DiscoveryResources(registry.client))


class TestDiscoveryResourcesOnNats(ServiceResourcesContract):
    base = "acme"
    sized = False

    def assert_shown(self, shown, text):
        assert shown is not None and f'"package_version": "{text}"' in shown

    @pytest.fixture
    def resources(self, discovery):
        return discovery


def test_modules_are_containers_with_their_instances(discovery):
    modules = {e.id: e for e in asyncio.run(discovery.list("")).entries}

    assert set(modules) == {"acme", "zeta"}
    assert modules["acme"].kind == "container"
    assert modules["acme"].attributes["instances"] == "3"
    assert modules["acme"].attributes["status"] == "STARTING 3"


def test_reading_an_instance_shows_its_descriptor(discovery):
    detail = asyncio.run(discovery.read("zeta/z-1"))

    assert detail.entry.attributes["status"] == "STARTING"
    assert '"module_id": "zeta"' in detail.content.text
    assert '"name": "Researcher"' in detail.content.text
    assert "lease_expires_at" in detail.content.text


def test_an_identity_that_may_not_evict_gets_a_reason(broker):
    from naas_abi_core.services.iam.tests.authorization_contract import contract_iam
    from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement

    iam = contract_iam()
    harness = IAMHarness(iam)
    viewer = harness.service_account("viewer")
    harness.grant(
        viewer.id,
        statement(
            "Allow",
            ["discovery:ListModules", "discovery:GetModule"],
            ["abi:-:-:discovery:module/*"],
        ),
    )
    registry = Registry(broker, identity="viewer", iam=iam)
    broker.run(registry.start())
    try:
        discovery = OnLoop(broker, DiscoveryResources(registry.client))
        with pytest.raises(SourceUnavailable, match="discovery:Evict"):
            asyncio.run(discovery.delete("acme/alpha"))
        assert "alpha" in {e.name for e in asyncio.run(discovery.list("acme")).entries}
    finally:
        broker.run(registry.stop())
