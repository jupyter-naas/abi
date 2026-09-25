import asyncio
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

from naas_abi_sdk.discovery import (
    DiscoveryClient,
    DiscoveryConfiguration,
    DiscoverySession,
    ModulesProxy,
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
