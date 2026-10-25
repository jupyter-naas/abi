import asyncio
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

from naas_abi_sdk.discovery import (
    PROCESS_DESCRIPTION_BYTES,
    DiscoveryClient,
    DiscoveryConfiguration,
    DiscoverySession,
    ModuleProxy,
    ModulesProxy,
    module_descriptor,
)
from naas_abi_sdk.transport import RPCError


def test_proxies_hide_proto_and_recheck_readiness():
    transport = AsyncMock()
    transport.call.return_value = pb.GetModuleResponse(
        instances=[
            pb.Instance(
                descriptor=pb.ModuleDescriptor(
                    module_id="provider",
                    contract_major=1,
                    agents=[pb.AgentDescriptor(name="Researcher", contract_major=1)],
                ),
                instance_id="one",
                status="READY",
            )
        ]
    )
    modules = ModulesProxy(DiscoveryClient(transport), ("provider",))
    assert asyncio.run(modules["provider"].list_agents())[0].name == "Researcher"
    with pytest.raises(ValueError, match="did not declare"):
        modules["other"]
    transport.call.return_value.instances[0].status = "DEGRADED"
    with pytest.raises(RPCError, match="MODULE_UNAVAILABLE"):
        asyncio.run(modules["provider"].list_agents())


def test_dependency_startup_is_bounded_and_auth_failure_not_retried():
    transport = AsyncMock()
    modules = ModulesProxy(DiscoveryClient(transport), ("missing",))
    transport.call.side_effect = RPCError("MODULE_NOT_FOUND", "missing")
    with pytest.raises(RPCError, match="DEPENDENCY_TIMEOUT"):
        asyncio.run(
            modules.wait_ready(
                DiscoveryConfiguration(startup_timeout=0.02, refresh_seconds=0.001)
            )
        )
    transport.call.reset_mock()
    transport.call.side_effect = RPCError("UNAUTHENTICATED", "invalid token")
    with pytest.raises(RPCError, match="UNAUTHENTICATED"):
        asyncio.run(modules.wait_ready(DiscoveryConfiguration()))
    transport.call.assert_awaited_once()


def test_lease_status_expires_locally_and_cleanup_survives_heartbeat_failure():
    async def scenario():
        client = DiscoveryClient(AsyncMock())
        session = DiscoverySession(
            client, pb.ModuleDescriptor(module_id="a", contract_major=1)
        )
        session.status = "READY"
        session.confirmed_until = 0
        assert session.current_status == "UNAVAILABLE"

        async def fail():
            raise RuntimeError("heartbeat failed")

        session.task = asyncio.create_task(fail())
        await asyncio.sleep(0)
        await session.close()
        assert session.current_status == "UNAVAILABLE"
        assert client.transport.call.call_args.args[0].endswith(".unregister")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "kwargs",
    [{"project": "a.*"}, {"startup_timeout": float("inf")}, {"refresh_seconds": 0}],
)
def test_discovery_config_rejects_unsafe_subjects_and_unbounded_timeouts(kwargs):
    with pytest.raises(ValueError):
        DiscoveryConfiguration(**kwargs)


def test_endpoint_rebinding_must_succeed_before_ready_renewal():
    async def scenario():
        client = DiscoveryClient(AsyncMock())
        client.transport.call.side_effect = [
            pb.RegisterResponse(
                instance=pb.Instance(status="STARTING"), lease_seconds=20
            ),
            pb.RenewResponse(instance=pb.Instance(status="READY"), lease_seconds=20),
        ]
        session = DiscoverySession(
            client, pb.ModuleDescriptor(module_id="a", contract_major=1)
        )
        session.initialized = True
        session.on_registered = AsyncMock(
            side_effect=[ConnectionError("bind failed"), None]
        )
        with pytest.raises(ConnectionError):
            await session.register()
        assert session.current_status == "STARTING"
        await session.renew()
        assert session.on_registered.await_count == 2
        assert session.current_status == "READY"

    asyncio.run(scenario())


def test_heartbeat_backoff_recovers_transient_errors_but_stops_on_bad_credentials(
    monkeypatch,
):
    async def scenario():
        delays = []
        sleep = asyncio.sleep

        async def fast_sleep(delay):
            delays.append(delay)
            await sleep(0)

        monkeypatch.setattr("naas_abi_sdk.discovery.asyncio.sleep", fast_sleep)
        session = DiscoverySession(
            DiscoveryClient(AsyncMock()),
            pb.ModuleDescriptor(module_id="a", contract_major=1),
        )
        session.renew = AsyncMock(
            side_effect=[
                RPCError("UNAVAILABLE", "down"),
                None,
                RPCError("UNAUTHENTICATED", "bad token"),
            ]
        )
        with pytest.raises(RPCError, match="UNAUTHENTICATED"):
            await session._heartbeat()
        assert session.renew.await_count == 3
        assert delays[1] > delays[0]
        assert delays[2] < delays[1]
        assert session.status == "UNAVAILABLE"

    asyncio.run(scenario())


def test_retry_schedule_recovers_before_lease_expiry(monkeypatch):
    from types import SimpleNamespace

    async def scenario():
        now = [0.0]
        sleep = asyncio.sleep
        monkeypatch.setattr(
            "naas_abi_sdk.discovery.time", SimpleNamespace(monotonic=lambda: now[0])
        )
        monkeypatch.setattr("naas_abi_sdk.discovery.random.uniform", lambda *_: 1.1)

        async def advance(delay):
            now[0] += delay
            await sleep(0)

        monkeypatch.setattr("naas_abi_sdk.discovery.asyncio.sleep", advance)
        session = DiscoverySession(
            DiscoveryClient(AsyncMock()),
            pb.ModuleDescriptor(module_id="a", contract_major=1),
        )
        session.confirmed_until = 20
        original_id = session.instance_id
        attempts = []

        async def renew():
            attempts.append(now[0])
            if len(attempts) < 3:
                raise RPCError("UNAVAILABLE", "temporary outage")
            assert now[0] < 20
            raise asyncio.CancelledError()

        session.renew = renew
        with pytest.raises(asyncio.CancelledError):
            await session._heartbeat()
        assert len(attempts) == 3
        assert session.instance_id == original_id
        now[0] = 30
        assert 0.05 <= session._heartbeat_delay(100) <= 10

    asyncio.run(scenario())


def test_a_lost_lease_registers_again_under_the_same_instance_id(monkeypatch):
    async def scenario():
        sleep = asyncio.sleep

        async def fast_sleep(delay):
            await sleep(0)

        monkeypatch.setattr("naas_abi_sdk.discovery.asyncio.sleep", fast_sleep)
        client = DiscoveryClient(AsyncMock())
        session = DiscoverySession(
            client, pb.ModuleDescriptor(module_id="a", contract_major=1)
        )
        first_id, first_token = session.instance_id, session.lease_token
        bound = []

        async def bind():
            bound.append(session.instance_id)

        session.on_registered = bind
        sent = []

        async def call(subject, request, response_type):
            operation = subject.rsplit(".", 1)[1]
            sent.append((operation, request))
            if operation == "renew" and len(sent) == 1:
                raise RPCError("LEASE_EXPIRED", "evicted")
            if operation == "register":
                return pb.RegisterResponse(
                    instance=pb.Instance(status="STARTING"), lease_seconds=20
                )
            raise asyncio.CancelledError()  # ends the heartbeat

        client.transport.call.side_effect = call
        with pytest.raises(asyncio.CancelledError):
            await session._heartbeat()

        assert [operation for operation, _ in sent] == ["renew", "register", "renew"]
        registered = sent[1][1]
        # Same identity, so whatever this process serves keeps its address.
        assert registered.instance_id == session.instance_id == first_id
        assert registered.lease_token == session.lease_token != first_token
        assert sent[2][1].instance_id == first_id
        assert bound == [first_id]

    asyncio.run(scenario())


def test_evict_calls_the_admin_operation_and_returns_the_instance():
    transport = AsyncMock()
    transport.call.return_value = pb.EvictResponse(
        instance=pb.Instance(
            descriptor=pb.ModuleDescriptor(
                module_id="research",
                contract_major=2,
                dependencies=[pb.Dependency(module_id="store", contract_major=1)],
            ),
            instance_id="r-1",
            status="READY",
        )
    )

    evicted = asyncio.run(DiscoveryClient(transport, "zen").evict("r-1"))

    subject, request, response_type = transport.call.call_args.args
    assert subject == "abi.discovery.zen.v1.evict"
    assert request == pb.EvictRequest(instance_id="r-1")
    assert response_type is pb.EvictResponse
    assert (evicted.module_id, evicted.instance_id, evicted.contract_major) == (
        "research",
        "r-1",
        2,
    )
    assert evicted.dependencies == (("store", 1),)


def test_rollout_is_registered_and_draining_wakes_the_runner():
    async def scenario():
        client = DiscoveryClient(AsyncMock())
        client.transport.call.side_effect = [
            pb.RegisterResponse(
                instance=pb.Instance(status="STARTING"), lease_seconds=20
            ),
            pb.RenewResponse(instance=pb.Instance(status="DRAINING"), lease_seconds=20),
        ]
        session = DiscoverySession(
            client,
            pb.ModuleDescriptor(module_id="a", contract_major=1),
            rollout_id="release-2",
            rollout_modules=("a", "b"),
        )
        await session.register()
        request = client.transport.call.call_args.args[1]
        assert request.rollout_id == "release-2"
        assert list(request.rollout_modules) == ["a", "b"]
        await session.renew()
        assert session.draining is True
        assert session.drain_requested.is_set()

    asyncio.run(scenario())


def test_rollout_configuration_rejects_a_cohort_without_an_id():
    with pytest.raises(ValueError, match="rollout id"):
        DiscoveryConfiguration(rollout_modules=("a",))


class _Process:
    """What module_descriptor reads of a workflow or pipeline class."""

    def __init__(self, text):
        self.text = text

    def description(self):
        return self.text


def _module_with(workflows, pipelines):
    class Module:
        package_version, contract_major, agents = "1.2.3", 4, ()

        @classmethod
        def get_workflow_classes(cls):
            return workflows

        @classmethod
        def get_pipeline_classes(cls):
            return pipelines

    return Module


def test_the_descriptor_declares_the_workflows_and_pipelines():
    module = _module_with(
        {"greet": _Process("Say hello."), "plain": _Process("plain")},
        {"load": _Process("Load " + "x" * 2000)},
    )
    descriptor = module_descriptor(module, "acme.mod", ())
    declared = {(p.kind, p.name): p for p in descriptor.processes}
    assert set(declared) == {
        ("workflow", "greet"),
        ("workflow", "plain"),
        ("pipeline", "load"),
    }
    assert declared[("workflow", "greet")].description == "Say hello."
    assert all(p.contract_major == 1 for p in descriptor.processes)
    # Discovery bounds the registry snapshot: only the start of a long text is kept.
    long = declared[("pipeline", "load")].description
    assert len(long.encode()) <= PROCESS_DESCRIPTION_BYTES and long.endswith("…")
    # A module type without them (or an older one) declares none.
    assert not module_descriptor(
        type("Bare", (), {"package_version": "0", "contract_major": 1, "agents": ()}),
        "m",
        (),
    ).processes


def test_instances_list_their_processes():
    transport = AsyncMock()
    transport.call.return_value = pb.GetModuleResponse(
        instances=[
            pb.Instance(
                descriptor=pb.ModuleDescriptor(
                    module_id="provider",
                    contract_major=1,
                    processes=[
                        pb.ProcessDescriptor(
                            name="greet",
                            kind="workflow",
                            description="Hi",
                            contract_major=1,
                        )
                    ],
                ),
                instance_id="one",
                status="READY",
            ),
            # An older module, or one without any.
            pb.Instance(
                descriptor=pb.ModuleDescriptor(module_id="provider", contract_major=1),
                instance_id="two",
                status="READY",
            ),
        ]
    )
    first, second = asyncio.run(DiscoveryClient(transport).get_module("provider"))
    assert [
        (p.name, p.kind, p.description, p.contract_major) for p in first.processes
    ] == [("greet", "workflow", "Hi", 1)]
    assert second.processes == ()


def test_get_workflow_and_get_pipeline_send_nothing_until_used():
    client = DiscoveryClient(AsyncMock())
    proxy = ModuleProxy(client, "provider")
    workflow, pipeline = proxy.get_workflow("greet"), proxy.get_pipeline("load")
    assert (workflow.kind, workflow.name) == ("workflow", "greet")
    assert (pipeline.kind, pipeline.name) == ("pipeline", "load")
    client.transport.call.assert_not_called()


@pytest.mark.parametrize(
    "text", ["日本語" * 600, "😀" * 600, "é" * 600, "ascii " * 600]
)
def test_a_description_is_cut_in_bytes_on_a_character_boundary(text):
    module = _module_with({"greet": _Process(text)}, {})
    (declared,) = module_descriptor(module, "m", ()).processes
    raw = declared.description.encode("utf-8")  # valid UTF-8, or this raises
    assert 0 < len(raw) <= PROCESS_DESCRIPTION_BYTES
    assert declared.description.endswith("…")
    assert text.startswith(declared.description[:-1])
    # What fits is left whole.
    short = module_descriptor(_module_with({"g": _Process("日本語")}, {}), "m", ())
    assert short.processes[0].description == "日本語"


def test_the_most_processes_the_service_allows_always_fit_its_byte_cap():
    # 128 processes with the longest names and the widest characters.
    classes = {f"{'n' * 60}{i:04d}": _Process("😀" * 5000) for i in range(128)}
    descriptor = module_descriptor(_module_with(classes, {}), "m", ())
    assert sum(p.ByteSize() for p in descriptor.processes) <= 128 * 1024
