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


def registration(name, id, dependencies=(), rollout="", contract=1, cohort=()):
    return pb.RegisterRequest(
        descriptor=pb.ModuleDescriptor(
            module_id=name,
            contract_major=contract,
            dependencies=[
                pb.Dependency(module_id=d, contract_major=1) for d in dependencies
            ],
        ),
        instance_id=id,
        lease_token="a" * 32 + id,
        rollout_id=rollout,
        rollout_modules=cohort,
    )


async def _up(service, req):
    await service.register(req, "owner")
    return await service.renew(
        pb.RenewRequest(
            instance_id=req.instance_id,
            lease_token=req.lease_token,
            initialized=True,
        ),
        "owner",
    )


async def _statuses(service, name, contract=1):
    result = await service.get_module(
        pb.GetModuleRequest(module_id=name, contract_major=contract)
    )
    return {item.instance_id: item.status for item in result.instances}


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


def test_model_authorization_requires_provider_lease_and_readiness():
    async def scenario():
        service = DiscoveryService(MemoryRegistry())
        req = registration("provider", "instance")
        req.descriptor.models.add(name="writer", kind="chat")
        await service.register(req, "provider-identity")
        auth = pb.AuthorizeModelRequest(
            instance_id="instance",
            lease_token=req.lease_token,
            model_name="writer",
        )
        with pytest.raises(DiscoveryError, match="MODULE_UNAVAILABLE"):
            await service.authorize_model(auth, "provider-identity")
        await service.renew(
            pb.RenewRequest(
                instance_id="instance", lease_token=req.lease_token, initialized=True
            ),
            "provider-identity",
        )
        await service.authorize_model(auth, "provider-identity")
        auth.model_name = "missing"
        with pytest.raises(DiscoveryError, match="MODEL_NOT_FOUND"):
            await service.authorize_model(auth, "provider-identity")

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


def test_agent_authorization_requires_provider_lease_and_readiness():
    async def scenario():
        service = DiscoveryService(MemoryRegistry())
        req = registration("provider", "instance")
        req.descriptor.agents.add(
            name="Researcher", contract_major=1, capabilities=["agent.invoke.v1"]
        )
        await service.register(req, "provider-identity")
        auth = pb.AuthorizeAgentRequest(
            instance_id="instance",
            lease_token=req.lease_token,
            agent_name="Researcher",
            new_invocation=True,
        )
        with pytest.raises(DiscoveryError, match="MODULE_UNAVAILABLE"):
            await service.authorize_agent(auth, "provider-identity")
        await service.renew(
            pb.RenewRequest(
                instance_id="instance", lease_token=req.lease_token, initialized=True
            ),
            "provider-identity",
        )
        await service.authorize_agent(auth, "provider-identity")
        with pytest.raises(DiscoveryError, match="PERMISSION_DENIED"):
            await service.authorize_agent(auth, "other-identity")
        auth.lease_token = "wrong"
        with pytest.raises(DiscoveryError, match="PERMISSION_DENIED"):
            await service.authorize_agent(auth, "provider-identity")

    asyncio.run(scenario())


def _with_jobs(request, *jobs):
    request.descriptor.jobs.extend(jobs)
    return request


def _job(name="ingest", kind="cron", spec="0 0 6 * * *", **fields):
    return pb.JobDescriptor(
        name=name,
        contract_major=1,
        triggers=[pb.JobTrigger(kind=kind, spec=spec)],
        max_concurrency=fields.pop("max_concurrency", 1),
        max_attempts=fields.pop("max_attempts", 1),
        **fields,
    )


def test_job_descriptors_are_validated():
    async def register(request):
        service = DiscoveryService(
            MemoryRegistry(), lease_seconds=20, clock=lambda: 0.0
        )
        await service.register(request, "owner")

    asyncio.run(
        register(
            _with_jobs(registration("m", "i"), _job(), _job("summary", "every", "1h"))
        )
    )

    invalid = [
        _with_jobs(registration("m", "i"), _job(), _job()),  # duplicate
        _with_jobs(registration("m", "i"), _job(name="bad name")),
        _with_jobs(registration("m", "i"), _job(kind="weekly")),
        _with_jobs(registration("m", "i"), _job(spec="")),
        _with_jobs(registration("m", "i"), _job(max_concurrency=0)),
        _with_jobs(registration("m", "i"), _job(max_attempts=0)),
        _with_jobs(registration("m", "i"), *[_job(f"j{i}") for i in range(129)]),
    ]
    for request in invalid:
        with pytest.raises(DiscoveryError, match="INVALID_ARGUMENT"):
            asyncio.run(register(request))


def test_replicas_must_declare_identical_jobs():
    async def scenario():
        service = DiscoveryService(
            MemoryRegistry(), lease_seconds=20, clock=lambda: 0.0
        )
        await service.register(_with_jobs(registration("m", "i1"), _job()), "owner")
        with pytest.raises(DiscoveryError, match="DESCRIPTOR_CONFLICT"):
            await service.register(
                _with_jobs(registration("m", "i2"), _job(spec="0 0 7 * * *")), "owner"
            )

    asyncio.run(scenario())


def test_platform_admins_evict_and_the_owner_must_register_again():
    async def scenario():
        service = DiscoveryService(
            MemoryRegistry(), lease_seconds=20, clock=lambda: 0.0
        )
        stuck = registration("research", "r-1")
        await service.register(stuck, "research")

        evicted = await service.evict(pb.EvictRequest(instance_id="r-1"), "api")

        assert evicted.instance.instance_id == "r-1"
        assert evicted.instance.descriptor.module_id == "research"
        listed = await service.list_modules(pb.ListModulesRequest(limit=10))
        assert [i.instance_id for i in listed.instances] == []
        # The evicted owner's lease is gone: it must register a fresh instance.
        with pytest.raises(DiscoveryError, match="LEASE_EXPIRED"):
            await service.renew(
                pb.RenewRequest(instance_id="r-1", lease_token=stuck.lease_token),
                "research",
            )

    asyncio.run(scenario())


def test_only_admin_identities_evict():
    async def scenario():
        service = DiscoveryService(
            MemoryRegistry(), clock=lambda: 0.0, admin_identities=("ops",)
        )
        await service.register(registration("research", "r-1"), "research")

        for caller in ("research", "api", "engine"):
            with pytest.raises(DiscoveryError, match="PERMISSION_DENIED"):
                await service.evict(pb.EvictRequest(instance_id="r-1"), caller)
        await service.evict(pb.EvictRequest(instance_id="r-1"), "ops")

    asyncio.run(scenario())


def test_default_admins_are_the_api_and_the_engine():
    async def scenario():
        service = DiscoveryService(MemoryRegistry(), clock=lambda: 0.0)
        for i, caller in enumerate(("api", "engine")):
            await service.register(registration("m", f"m-{i}"), "m")
            await service.evict(pb.EvictRequest(instance_id=f"m-{i}"), caller)
        with pytest.raises(DiscoveryError, match="PERMISSION_DENIED"):
            await service.evict(pb.EvictRequest(instance_id="m-0"), "m")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "instance_id,code",
    [
        ("missing", "INSTANCE_NOT_FOUND"),
        ("", "INVALID_ARGUMENT"),
        ("a/b", "INVALID_ARGUMENT"),
    ],
)
def test_evicting_an_unknown_or_malformed_instance_is_refused(instance_id, code):
    async def scenario():
        service = DiscoveryService(MemoryRegistry(), clock=lambda: 0.0)
        with pytest.raises(DiscoveryError, match=code):
            await service.evict(pb.EvictRequest(instance_id=instance_id), "api")

    asyncio.run(scenario())


def test_admin_identities_must_be_named():
    with pytest.raises(ValueError):
        DiscoveryService(MemoryRegistry(), admin_identities=("",))


def test_rollout_waits_for_the_cohort_then_drains_the_previous_generation():
    async def scenario():
        now = [0.0]
        service = DiscoveryService(MemoryRegistry(), clock=lambda: now[0])
        old_a, old_b = registration("a", "a-old"), registration("b", "b-old")
        await _up(service, old_a)
        await _up(service, old_b)
        now[0] = 10
        cohort = ("a", "b")
        new_a = registration("a", "a-new", rollout="release-2", cohort=cohort)
        await _up(service, new_a)
        assert await _statuses(service, "a") == {"a-old": "READY", "a-new": "STAGED"}
        assert (await _statuses(service, "b"))["b-old"] == "READY"
        new_b = registration("b", "b-new", rollout="release-2", cohort=cohort)
        await _up(service, new_b)
        assert await _statuses(service, "a") == {"a-old": "DRAINING", "a-new": "READY"}
        assert await _statuses(service, "b") == {"b-old": "DRAINING", "b-new": "READY"}

    asyncio.run(scenario())


def test_same_rollout_replica_joins_and_a_later_rollout_replaces_it():
    async def scenario():
        now = [0.0]
        service = DiscoveryService(MemoryRegistry(), clock=lambda: now[0])
        await _up(service, registration("a", "a1", rollout="release-1"))
        await _up(service, registration("a", "a2", rollout="release-1"))
        assert await _statuses(service, "a") == {"a1": "READY", "a2": "READY"}
        now[0] = 5
        await _up(service, registration("a", "a3", rollout="release-2", contract=2))
        assert await _statuses(service, "a") == {"a1": "DRAINING", "a2": "DRAINING"}
        assert await _statuses(service, "a", contract=2) == {"a3": "READY"}

    asyncio.run(scenario())


def _with_agent(request, name="Researcher"):
    request.descriptor.agents.add(
        name=name, contract_major=1, capabilities=["agent.invoke.v1"]
    )
    return request


def test_a_new_rollout_may_add_jobs_and_agents_and_waits_for_its_cohort():
    async def scenario():
        now = [0.0]
        service = DiscoveryService(MemoryRegistry(), clock=lambda: now[0])
        await _up(service, _with_jobs(registration("a", "a-old"), _job()))
        await _up(service, registration("b", "b-old"))
        now[0] = 10
        cohort = ("a", "b")
        # Same contract major: a new job and a changed schedule on a, an agent on b.
        new_a = registration("a", "a-new", rollout="release-2", cohort=cohort)
        _with_jobs(new_a, _job(spec="0 0 7 * * *"), _job("summary", "every", "1h"))
        new_b = _with_agent(
            registration("b", "b-new", rollout="release-2", cohort=cohort)
        )
        await _up(service, new_a)
        assert await _statuses(service, "a") == {"a-old": "READY", "a-new": "STAGED"}
        await _up(service, new_b)
        assert await _statuses(service, "a") == {"a-old": "DRAINING", "a-new": "READY"}
        assert await _statuses(service, "b") == {"b-old": "DRAINING", "b-new": "READY"}

    asyncio.run(scenario())


def test_a_single_module_rollout_with_a_new_job_replaces_the_live_one():
    async def scenario():
        now = [0.0]
        service = DiscoveryService(MemoryRegistry(), clock=lambda: now[0])
        await _up(service, registration("a", "v1", rollout="release-1"))
        now[0] = 10
        v2 = _with_jobs(registration("a", "v2", rollout="release-2"), _job())
        await _up(service, v2)
        assert await _statuses(service, "a") == {"v1": "DRAINING", "v2": "READY"}

    asyncio.run(scenario())


def test_replicas_of_one_generation_still_declare_identical_descriptors():
    async def scenario():
        service = DiscoveryService(MemoryRegistry(), clock=lambda: 0.0)
        await _up(service, registration("a", "old"))
        first = _with_jobs(registration("a", "r2-1", rollout="release-2"), _job())
        await service.register(first, "owner")
        # Another replica of that rollout must match it, even with a live old one.
        for differs in (
            registration("a", "r2-2", rollout="release-2"),
            _with_jobs(registration("a", "r2-2", rollout="release-2"), _job("other")),
            _with_agent(
                _with_jobs(registration("a", "r2-2", rollout="release-2"), _job())
            ),
        ):
            with pytest.raises(DiscoveryError, match="DESCRIPTOR_CONFLICT"):
                await service.register(differs, "owner")
        same = _with_jobs(registration("a", "r2-2", rollout="release-2"), _job())
        await service.register(same, "owner")
        # Without rollout ids, every live replica is one generation.
        with pytest.raises(DiscoveryError, match="DESCRIPTOR_CONFLICT"):
            await service.register(_with_agent(registration("a", "plain")), "owner")

    asyncio.run(scenario())


def test_first_rollout_becomes_ready_and_a_missing_dependency_blocks_cutover():
    async def scenario():
        service = DiscoveryService(MemoryRegistry(), clock=lambda: 0.0)
        cohort = ("a", "b")
        await _up(service, registration("b", "b1", rollout="release-1", cohort=cohort))
        await _up(
            service, registration("a", "a1", ("b",), rollout="release-1", cohort=cohort)
        )
        assert (await _statuses(service, "a"))["a1"] == "READY"
        assert (await _statuses(service, "b"))["b1"] == "READY"
        blocked = DiscoveryService(MemoryRegistry(), clock=lambda: 0.0)
        await _up(blocked, registration("a", "a-old"))
        await _up(
            blocked,
            registration("a", "a-new", ("missing",), rollout="release-2", contract=2),
        )
        assert (await _statuses(blocked, "a"))["a-old"] == "READY"
        assert (await _statuses(blocked, "a", contract=2))["a-new"] == "STAGED"
        with pytest.raises(DiscoveryError, match="Invalid rollout id"):
            await service.register(
                registration("a", "bad", rollout="not valid"), "owner"
            )

    asyncio.run(scenario())


async def _renew(service, req):
    return await service.renew(
        pb.RenewRequest(
            instance_id=req.instance_id, lease_token=req.lease_token, initialized=True
        ),
        "owner",
    )


def test_the_serving_generation_keeps_serving_when_its_rollout_breaks():
    async def scenario():
        now = [0.0]
        service = DiscoveryService(
            MemoryRegistry(), lease_seconds=20, clock=lambda: now[0]
        )
        cohort = ("a", "b")
        old_a = registration("a", "a-old", rollout="release-1", cohort=cohort)
        await _up(service, old_a)
        await _up(
            service, registration("b", "b-old", rollout="release-1", cohort=cohort)
        )
        now[0] = 10
        new_a = registration("a", "a-new", rollout="release-2", cohort=cohort)
        await _up(service, new_a)
        assert await _statuses(service, "a") == {"a-old": "READY", "a-new": "STAGED"}
        now[0] = 15
        await _renew(service, old_a)
        now[0] = 25  # b-old's lease ran out: release-1 is no longer complete
        await _renew(service, new_a)
        assert await _statuses(service, "a") == {"a-old": "READY", "a-new": "STAGED"}
        # A replacement replica of the serving generation is not staged either.
        await _up(
            service, registration("a", "a-old-2", rollout="release-1", cohort=cohort)
        )
        assert (await _statuses(service, "a"))["a-old-2"] == "READY"
        # release-2 completes, takes over and drains the incomplete release-1.
        await _up(
            service, registration("b", "b-new", rollout="release-2", cohort=cohort)
        )
        assert await _statuses(service, "a") == {
            "a-old": "DRAINING",
            "a-old-2": "DRAINING",
            "a-new": "READY",
        }

    asyncio.run(scenario())


def test_an_incomplete_generation_serves_until_none_of_its_instances_is_left():
    async def scenario():
        now = [0.0]
        service = DiscoveryService(
            MemoryRegistry(), lease_seconds=20, clock=lambda: now[0]
        )
        cohort = ("a", "b", "c")  # b never comes up: no rollout completes
        other = registration("c", "c-1", rollout="release-1", cohort=cohort)
        await _up(service, other)
        await _up(service, registration("a", "a-1", rollout="release-1", cohort=cohort))
        now[0] = 5
        second = registration("a", "a-2", rollout="release-2", cohort=cohort)
        await _up(service, second)
        # The oldest generation serves first, and keeps serving.
        assert await _statuses(service, "a") == {"a-1": "READY", "a-2": "STAGED"}
        now[0] = 15
        await _renew(service, other)
        await _renew(service, second)
        now[0] = 22  # a-1's lease ran out: release-2 is the only one left for a
        await _renew(service, second)
        assert await _statuses(service, "a") == {"a-2": "READY"}
        # A late replica of the older release-1 does not take a-2's place back.
        await _up(
            service, registration("a", "a-1b", rollout="release-1", cohort=cohort)
        )
        assert await _statuses(service, "a") == {"a-2": "READY", "a-1b": "STAGED"}

    asyncio.run(scenario())


async def _flip_a_dependency(order):
    now = [0.0]
    service = DiscoveryService(MemoryRegistry(), clock=lambda: now[0])
    await _up(service, registration("a", "a-old", ("b",)))
    await _up(service, registration("b", "b-old"))
    now[0] = 10
    cohort = ("a", "b")
    # release-2 reverses the edge: b depends on a, and a no longer on b.
    new = {
        "a": registration("a", "a-new", rollout="release-2", cohort=cohort),
        "b": registration("b", "b-new", ("a",), rollout="release-2", cohort=cohort),
    }
    for name in order:
        await _up(service, new[name])
    return await _statuses(service, "a"), await _statuses(service, "b")


def test_a_rollout_may_reverse_a_dependency_between_the_modules_it_replaces():
    for order in (("b", "a"), ("a", "b")):
        assert asyncio.run(_flip_a_dependency(order)) == (
            {"a-old": "DRAINING", "a-new": "READY"},
            {"b-old": "DRAINING", "b-new": "READY"},
        )


def test_cycles_within_a_generation_or_with_one_that_can_serve_beside_it_are_refused():
    async def scenario():
        service = DiscoveryService(MemoryRegistry(), clock=lambda: 0.0)
        await _up(service, registration("a", "a-old"))
        await _up(service, registration("c", "c-old", ("a",)))
        cohort = ("a", "b")
        await service.register(
            registration("a", "a-2", ("b",), rollout="release-2", cohort=cohort),
            "owner",
        )
        # Within one generation.
        with pytest.raises(DiscoveryError, match="DEPENDENCY_CYCLE"):
            await service.register(
                registration("b", "b-2", ("a",), rollout="release-2", cohort=cohort),
                "owner",
            )
        # With the generation serving c, which release-3 does not replace.
        with pytest.raises(DiscoveryError, match="DEPENDENCY_CYCLE"):
            await service.register(
                registration("a", "a-3", ("c",), rollout="release-3"), "owner"
            )
        # With release-2's staged a: both rollouts could serve side by side.
        with pytest.raises(DiscoveryError, match="DEPENDENCY_CYCLE"):
            await service.register(
                registration("b", "b-4", ("a",), rollout="release-4"), "owner"
            )
        # Unrelated modules and acyclic edges still register.
        await service.register(
            registration("d", "d-1", ("a", "c"), rollout="release-5"), "owner"
        )

    asyncio.run(scenario())


class CountingRegistry(MemoryRegistry):
    """Counts full snapshot reads (each one up to 512 KiB from JetStream)."""

    def __init__(self):
        super().__init__()
        self.reads = 0

    async def read(self):
        self.reads += 1
        return await super().read()


def _provider(instance="instance"):
    req = registration("provider", instance)
    req.descriptor.agents.add(
        name="Researcher", contract_major=1, capabilities=["agent.invoke.v1"]
    )
    return req


def _poll(req, new_invocation=False):
    return pb.AuthorizeAgentRequest(
        instance_id=req.instance_id,
        lease_token=req.lease_token,
        agent_name="Researcher",
        new_invocation=new_invocation,
    )


def test_agent_polls_are_authorized_from_a_recent_snapshot():
    async def scenario():
        now = [0.0]
        registry = CountingRegistry()
        service = DiscoveryService(registry, clock=lambda: now[0])
        req = _provider()
        await _up(service, req)
        reads = registry.reads
        for _ in range(50):  # status and event polls
            await service.authorize_agent(_poll(req), "owner")
        assert registry.reads == reads
        # A submit always reads the registry: it needs the provider READY.
        await service.authorize_agent(_poll(req, new_invocation=True), "owner")
        assert registry.reads == reads + 1
        # The snapshot is reused for at most a second.
        now[0] += 1
        await service.authorize_agent(_poll(req), "owner")
        await service.authorize_agent(_poll(req), "owner")
        assert registry.reads == reads + 2

    asyncio.run(scenario())


def test_a_snapshot_never_refuses_what_the_registry_allows():
    async def scenario():
        registry = CountingRegistry()
        # Two discovery replicas share one registry.
        first = DiscoveryService(registry, clock=lambda: 0.0)
        second = DiscoveryService(registry, clock=lambda: 0.0)
        await _up(first, _provider("old"))
        await first.authorize_agent(_poll(_provider("old")), "owner")
        # Registered through the other replica after that snapshot.
        late = _provider("late")
        await _up(second, late)
        await first.authorize_agent(_poll(late), "owner")
        # Registered again with a new lease token after an eviction.
        await second.evict(pb.EvictRequest(instance_id="late"), "api")
        late.lease_token = "b" * 40
        await _up(second, late)
        await first.authorize_agent(_poll(late), "owner")

    asyncio.run(scenario())


def test_registry_changes_end_snapshot_answers():
    async def scenario():
        now = [0.0]
        registry = CountingRegistry()
        first = DiscoveryService(registry, lease_seconds=5, clock=lambda: now[0])
        second = DiscoveryService(registry, lease_seconds=5, clock=lambda: now[0])
        evicted, gone, lapsed = (_provider(i) for i in ("evicted", "gone", "lapsed"))
        keeper = _provider("keeper")
        for req in (evicted, gone, lapsed, keeper):
            await _up(first, req)
            await first.authorize_agent(_poll(req), "owner")
        # A change through this replica applies at once.
        await first.evict(pb.EvictRequest(instance_id="evicted"), "api")
        with pytest.raises(DiscoveryError, match="LEASE_EXPIRED"):
            await first.authorize_agent(_poll(evicted), "owner")
        # A change through another replica: the snapshot allows it for at most
        # a second, then a fresh read refuses it.
        await second.unregister(
            pb.UnregisterRequest(instance_id="gone", lease_token=gone.lease_token),
            "owner",
        )
        now[0] = 0.5
        await first.authorize_agent(_poll(gone), "owner")
        now[0] = 1.0
        with pytest.raises(DiscoveryError, match="LEASE_EXPIRED"):
            await first.authorize_agent(_poll(gone), "owner")
        # Leases are checked against the clock, not the snapshot's time.
        now[0] = 4.5
        await first.renew(
            pb.RenewRequest(instance_id="keeper", lease_token=keeper.lease_token),
            "owner",
        )
        now[0] = 5.2  # "lapsed" expired at 5; the snapshot is from 4.5
        with pytest.raises(DiscoveryError, match="LEASE_EXPIRED"):
            await first.authorize_agent(_poll(lapsed), "owner")
        await first.authorize_agent(_poll(keeper), "owner")

    asyncio.run(scenario())


def test_snapshot_refusals_are_rechecked_and_still_refused():
    async def scenario():
        registry = CountingRegistry()
        service = DiscoveryService(registry, clock=lambda: 0.0)
        req = _provider()
        await _up(service, req)
        reads = registry.reads
        wrong = _poll(req)
        wrong.lease_token = "wrong"
        with pytest.raises(DiscoveryError, match="PERMISSION_DENIED"):
            await service.authorize_agent(wrong, "owner")
        with pytest.raises(DiscoveryError, match="PERMISSION_DENIED"):
            await service.authorize_agent(_poll(req), "intruder")
        missing = _poll(req)
        missing.agent_name = "Missing"
        with pytest.raises(DiscoveryError, match="AGENT_NOT_FOUND"):
            await service.authorize_agent(missing, "owner")
        assert registry.reads == reads + 3

    asyncio.run(scenario())


class YieldingRegistry(MemoryRegistry):
    """Like the JetStream KV: each read and write lets other calls run."""

    async def read(self):
        await asyncio.sleep(0)
        return await super().read()

    async def compare_and_swap(self, data, revision):
        await asyncio.sleep(0)
        await super().compare_and_swap(data, revision)


def test_concurrent_registrations_in_one_process_all_succeed():
    async def scenario():
        service = DiscoveryService(YieldingRegistry())
        # The NATS endpoint runs calls side by side: without serializing its
        # own mutations, they would exhaust the CAS retries (REGISTRY_BUSY).
        await asyncio.gather(
            *(
                service.register(registration(f"m{i}", f"i{i}"), "owner")
                for i in range(20)
            )
        )
        listed = await service.list_modules(pb.ListModulesRequest(limit=100))
        return {instance.instance_id for instance in listed.instances}

    assert asyncio.run(scenario()) == {f"i{i}" for i in range(20)}


class CountingWrites(YieldingRegistry):
    """Counts compare-and-swaps, each one a full snapshot written to JetStream."""

    def __init__(self):
        super().__init__()
        self.writes = 0

    async def compare_and_swap(self, data, revision):
        self.writes += 1
        await super().compare_and_swap(data, revision)


async def _listed(service):
    listed = await service.list_modules(pb.ListModulesRequest(limit=100))
    return {instance.instance_id for instance in listed.instances}


def test_mutations_that_arrive_together_share_one_registry_write():
    async def scenario():
        registry = CountingWrites()
        service = DiscoveryService(registry)
        await asyncio.gather(
            *(
                service.register(registration(f"m{i}", f"i{i}"), "owner")
                for i in range(20)
            )
        )
        return registry.writes, await _listed(service)

    writes, listed = asyncio.run(scenario())

    # The first goes alone; the 19 that arrive while it is written go together.
    assert writes == 2
    assert listed == {f"i{i}" for i in range(20)}


def test_a_mutation_that_fails_leaves_the_others_written_with_it():
    async def scenario():
        service = DiscoveryService(CountingWrites())
        results = await asyncio.gather(
            service.register(registration("a", "a"), "owner"),
            service.register(registration("b", "b"), "owner"),
            service.register(registration("bad.*", "bad"), "owner"),
            service.register(registration("c", "c"), "owner"),
            return_exceptions=True,
        )
        return results, await _listed(service)

    results, listed = asyncio.run(scenario())

    assert isinstance(results[2], DiscoveryError)
    assert "INVALID_ARGUMENT" in str(results[2])
    assert [r.instance.instance_id for r in (results[0], results[1], results[3])] == [
        "a",
        "b",
        "c",
    ]
    assert listed == {"a", "b", "c"}


def test_a_batch_is_applied_again_after_another_replica_writes_first():
    class Contended(CountingWrites):
        conflicts = 2

        async def compare_and_swap(self, data, revision):
            if self.conflicts:
                self.conflicts -= 1
                await asyncio.sleep(0)
                raise RevisionConflict()
            await super().compare_and_swap(data, revision)

    async def scenario():
        service = DiscoveryService(Contended())
        await asyncio.gather(
            *(
                service.register(registration(f"m{i}", f"i{i}"), "owner")
                for i in range(5)
            )
        )
        return await _listed(service)

    assert asyncio.run(scenario()) == {f"i{i}" for i in range(5)}


def test_a_registry_outage_fails_every_mutation_waiting_on_it():
    class Down(YieldingRegistry):
        async def read(self):
            await asyncio.sleep(0)
            raise ConnectionError("JetStream unavailable")

    async def scenario():
        service = DiscoveryService(Down())
        return await asyncio.wait_for(
            asyncio.gather(
                *(
                    service.register(registration(f"m{i}", f"i{i}"), "owner")
                    for i in range(5)
                ),
                return_exceptions=True,
            ),
            timeout=2,
        )

    results = asyncio.run(scenario())

    assert all(isinstance(result, ConnectionError) for result in results)


class GatedWrites(CountingWrites):
    """Holds write number ``gated`` (1-based) until ``release`` is set."""

    def __init__(self, gated):
        super().__init__()
        self.gated = gated
        self.release = asyncio.Event()
        self.held = asyncio.Event()

    async def compare_and_swap(self, data, revision):
        if self.writes + 1 == self.gated:
            self.held.set()
            await self.release.wait()
        await super().compare_and_swap(data, revision)


def test_a_mutation_cancelled_before_it_is_written_is_dropped():
    async def scenario():
        registry = GatedWrites(gated=1)
        service = DiscoveryService(registry)
        first = asyncio.create_task(service.register(registration("a", "a"), "owner"))
        await registry.held.wait()  # "a" is being written
        waiting = asyncio.create_task(service.register(registration("b", "b"), "owner"))
        await asyncio.sleep(0.01)
        waiting.cancel()
        registry.release.set()
        await first
        with pytest.raises(asyncio.CancelledError):
            await waiting
        return await _listed(service)

    assert asyncio.run(scenario()) == {"a"}


def test_a_writer_cancelled_mid_write_fails_the_mutations_written_with_it():
    async def scenario():
        registry = GatedWrites(gated=2)
        service = DiscoveryService(registry)
        first = asyncio.create_task(service.register(registration("a", "a"), "owner"))
        await asyncio.sleep(0)  # "a" takes the lock and starts its write
        writer = asyncio.create_task(service.register(registration("b", "b"), "owner"))
        joined = asyncio.create_task(service.register(registration("c", "c"), "owner"))
        await first
        await registry.held.wait()  # "b" writes "b" and "c" together
        writer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await writer
        with pytest.raises(DiscoveryError, match="UNAVAILABLE"):
            await asyncio.wait_for(joined, timeout=2)

    asyncio.run(scenario())
