import asyncio

import pytest
from naas_abi_core.services.discovery.discovery_ports import RevisionConflict
from naas_abi_core.services.discovery.discovery_service import (
    DiscoveryError,
    DiscoveryService,
)
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb


class MemoryRegistry:
    def __init__(self):
        self.data, self.revision = b"", 0

    async def read(self):
        return self.data, self.revision

    async def compare_and_swap(self, data, revision):
        if revision != self.revision:
            raise RevisionConflict()
        self.data, self.revision = data, self.revision + 1


def registration(name, id, dependencies=()):
    return pb.RegisterRequest(
        descriptor=pb.ModuleDescriptor(
            module_id=name,
            contract_major=1,
            dependencies=[
                pb.Dependency(module_id=d, contract_major=1) for d in dependencies
            ],
        ),
        instance_id=id,
        lease_token="a" * 32 + id,
    )


def test_readiness_dependency_loss_recovery_and_replicas():
    async def scenario():
        now = [0.0]
        service = DiscoveryService(
            MemoryRegistry(), lease_seconds=20, clock=lambda: now[0]
        )
        a, b = registration("a", "a", ("b",)), registration("b", "b")
        for r in (a, b):
            await service.register(r, "owner")
            await service.renew(
                pb.RenewRequest(
                    instance_id=r.instance_id,
                    lease_token=r.lease_token,
                    initialized=True,
                ),
                "owner",
            )
        assert (
            await service.get_module(
                pb.GetModuleRequest(module_id="a", contract_major=1)
            )
        ).instances[0].status == "READY"
        now[0] = 15
        await service.renew(
            pb.RenewRequest(
                instance_id="a", lease_token=a.lease_token, initialized=True
            ),
            "owner",
        )
        now[0] = 21
        assert (
            await service.get_module(
                pb.GetModuleRequest(module_id="a", contract_major=1)
            )
        ).instances[0].status == "DEGRADED"
        with pytest.raises(DiscoveryError, match="LEASE_EXPIRED"):
            await service.renew(
                pb.RenewRequest(
                    instance_id="b", lease_token=b.lease_token, initialized=True
                ),
                "owner",
            )
        for id in ("b2", "b3"):
            r = registration("b", id)
            await service.register(r, "owner")
            await service.renew(
                pb.RenewRequest(
                    instance_id=id, lease_token=r.lease_token, initialized=True
                ),
                "owner",
            )
        assert (
            len(
                (
                    await service.get_module(
                        pb.GetModuleRequest(module_id="b", contract_major=1)
                    )
                ).instances
            )
            == 2
        )
        assert (
            await service.get_module(
                pb.GetModuleRequest(module_id="a", contract_major=1)
            )
        ).instances[0].status == "READY"

    asyncio.run(scenario())


def test_cycles_ownership_idempotency_and_incompatible_contract():
    async def scenario():
        service = DiscoveryService(MemoryRegistry())
        a = registration("a", "a", ("b",))
        await service.register(a, "owner")
        await service.register(a, "owner")
        with pytest.raises(DiscoveryError, match="DEPENDENCY_CYCLE"):
            await service.register(registration("b", "b", ("a",)), "owner")
        with pytest.raises(DiscoveryError, match="PERMISSION_DENIED"):
            await service.unregister(
                pb.UnregisterRequest(instance_id="a", lease_token=a.lease_token),
                "other",
            )
        with pytest.raises(DiscoveryError, match="INCOMPATIBLE_MODULE"):
            await service.get_module(
                pb.GetModuleRequest(module_id="a", contract_major=2)
            )
        await service.unregister(
            pb.UnregisterRequest(instance_id="a", lease_token=a.lease_token), "owner"
        )
        await service.unregister(
            pb.UnregisterRequest(instance_id="a", lease_token=a.lease_token), "owner"
        )

    asyncio.run(scenario())


def test_cas_contention_retries_validation_and_pages_do_not_expose_credentials():
    class Contended(MemoryRegistry):
        conflicts = 2

        async def compare_and_swap(self, data, revision):
            if self.conflicts:
                self.conflicts -= 1
                raise RevisionConflict()
            await super().compare_and_swap(data, revision)

    async def scenario():
        service = DiscoveryService(Contended())
        for id in ("a", "b", "c"):
            await service.register(registration(id, id), "owner")
        first = await service.list_modules(pb.ListModulesRequest(limit=2))
        second = await service.list_modules(
            pb.ListModulesRequest(
                limit=2, after_instance_id=first.next_after_instance_id
            )
        )
        assert [i.instance_id for i in first.instances] + [
            i.instance_id for i in second.instances
        ] == ["a", "b", "c"]
        assert second.next_after_instance_id == ""
        assert b"owner" not in first.SerializeToString()
        assert b"a" * 32 not in first.SerializeToString()
        with pytest.raises(DiscoveryError, match="INVALID_ARGUMENT"):
            await service.register(registration("bad.*", "bad"), "owner")

    asyncio.run(scenario())


def test_register_retry_does_not_extend_lease_or_overstate_remaining_lifetime():
    async def scenario():
        now = [0.0]
        service = DiscoveryService(MemoryRegistry(), clock=lambda: now[0])
        request = registration("module", "instance")
        first = await service.register(request, "owner")
        now[0] = 15
        repeated = await service.register(request, "owner")
        assert repeated.instance.expires_at == first.instance.expires_at
        assert repeated.lease_seconds == 5

    asyncio.run(scenario())
