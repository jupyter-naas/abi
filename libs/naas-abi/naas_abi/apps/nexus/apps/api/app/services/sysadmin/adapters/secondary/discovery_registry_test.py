import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.discovery_registry import (
    DiscoveryModuleRegistry,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import ModuleRegistryContract
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi_sdk.discovery import AgentDescriptor, ModuleInstance
from naas_abi_sdk.jobs import Every, JobDescriptor
from naas_abi_sdk.transport import RPCError


def _instance(module_id, status, agent, jobs=()):
    return ModuleInstance(
        module_id=module_id,
        instance_id=f"{module_id}-1",
        package_version="0.1.0",
        contract_major=1,
        status=status,
        expires_at=1_900_000_000.0,
        agents=(AgentDescriptor(agent, "", 1, ("agent.invoke.v1",)),),
        jobs=jobs,
    )


class FakeDiscovery:
    """Two pages, like the registry answers with limit=1."""

    def __init__(self):
        self.pages = [
            (
                [
                    _instance(
                        "ops.researcher",
                        "READY",
                        "Researcher",
                        (JobDescriptor("digest", "Counts runs.", triggers=(Every("10m"),)),),
                    )
                ],
                "cursor-1",
            ),
            ([_instance("ops.orchestrator", "STARTING", "Orchestrator")], ""),
        ]
        self.calls = []

    async def list_modules(self, *, limit=100, after_instance_id=""):
        self.calls.append(after_instance_id)
        return self.pages[len(self.calls) - 1]


@pytest.fixture
def registry():
    return DiscoveryModuleRegistry(FakeDiscovery)


class TestDiscoveryModuleRegistry(ModuleRegistryContract):
    pass


def test_follows_the_cursor_until_the_last_page():
    fake = FakeDiscovery()
    asyncio.run(DiscoveryModuleRegistry(lambda: fake).list_instances())

    assert fake.calls == ["", "cursor-1"]


def test_registry_errors_mean_unavailable():
    class Failing:
        async def list_modules(self, **_):
            raise RPCError("UNAUTHENTICATED", "bad token")

    with pytest.raises(SourceUnavailable) as raised:
        asyncio.run(DiscoveryModuleRegistry(Failing).list_instances())
    assert raised.value.source == "discovery" and "UNAUTHENTICATED" in raised.value.reason
