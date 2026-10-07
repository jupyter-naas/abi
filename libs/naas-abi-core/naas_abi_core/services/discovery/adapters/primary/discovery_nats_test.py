import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.services.discovery.adapters.primary.discovery_nats import (
    DiscoveryNATS,
)
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

SECRET = "discovery-unit-test-secret-32-bytes"


def test_authentication_precedes_domain_mutations_and_binds_caller():
    async def scenario():
        service = AsyncMock()
        primary = DiscoveryNATS(service, SECRET, "test")
        service.register.return_value = pb.RegisterResponse()
        msg = SimpleNamespace(
            data=pb.RegisterRequest().SerializeToString(),
            headers={},
            reply="reply",
            respond=AsyncMock(),
            _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
        )
        await primary._handle("register", msg)
        assert (
            pb.RegisterResponse.FromString(
                msg._client.publish.call_args.args[1]
            ).error.code
            == "UNAUTHENTICATED"
        )
        service.register.assert_not_awaited()
        msg.headers = {"Nats-Auth-Token": issue_service_token("caller", SECRET)}
        await primary._handle("register", msg)
        assert service.register.call_args.args[1] == "caller"

    asyncio.run(scenario())


def test_evict_is_an_authenticated_admin_mutation():
    from naas_abi_core.services.discovery.adapters.primary.discovery_nats import (
        OPERATIONS,
    )
    from naas_abi_core.services.discovery.discovery_service import DiscoveryService
    from naas_abi_core.services.discovery.discovery_service_test import (
        MemoryRegistry,
        registration,
    )

    async def scenario():
        service = DiscoveryService(MemoryRegistry())
        await service.register(registration("research", "r-1"), "research")
        primary = DiscoveryNATS(service, SECRET, "test")

        async def evict_as(identity):
            msg = SimpleNamespace(
                data=pb.EvictRequest(instance_id="r-1").SerializeToString(),
                headers={"Nats-Auth-Token": issue_service_token(identity, SECRET)},
                reply="reply",
                respond=AsyncMock(),
                _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
            )
            await primary._handle("evict", msg)
            return pb.EvictResponse.FromString(msg._client.publish.call_args.args[1])

        assert OPERATIONS["evict"][2] is True
        assert (await evict_as("research")).error.code == "PERMISSION_DENIED"
        evicted = await evict_as("api")
        assert evicted.error.code == ""
        assert evicted.instance.instance_id == "r-1"
        assert (await evict_as("api")).error.code == "INSTANCE_NOT_FOUND"

    asyncio.run(scenario())


def test_an_overflow_uploaded_request_is_refused_as_too_large():
    # Discovery does not read overflow uploads: such a request arrives with an
    # empty body and must not be parsed as an empty (valid) request.
    async def scenario():
        service = AsyncMock()
        primary = DiscoveryNATS(service, SECRET, "test")
        msg = SimpleNamespace(
            data=b"",
            headers={
                "Nats-Auth-Token": issue_service_token("caller", SECRET),
                "Abi-Overflow-Request": f"{'a' * 32}:upload",
            },
            reply="reply",
            _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
        )
        await primary._handle("register", msg)
        response = pb.RegisterResponse.FromString(msg._client.publish.call_args.args[1])
        assert response.error.code == "PAYLOAD_TOO_LARGE"
        service.register.assert_not_awaited()

    asyncio.run(scenario())


def test_authorize_agent_names_the_caller_and_whether_it_is_an_admin():
    async def scenario():
        service = AsyncMock()
        service.admin_identities = frozenset({"api", "engine"})
        service.authorize_agent.return_value = pb.AuthorizeAgentResponse()
        primary = DiscoveryNATS(service, SECRET, "test")

        async def authorize(caller):
            msg = SimpleNamespace(
                data=pb.AuthorizeAgentRequest(
                    instance_id="r-1",
                    agent_name="Researcher",
                    caller_token=issue_service_token(caller, SECRET),
                ).SerializeToString(),
                headers={"Nats-Auth-Token": issue_service_token("research", SECRET)},
                reply="reply",
                _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
            )
            await primary._handle("authorize_agent", msg)
            return pb.AuthorizeAgentResponse.FromString(
                msg._client.publish.call_args.args[1]
            )

        module = await authorize("orchestrator")
        assert (module.caller_identity, module.caller_admin) == ("orchestrator", False)
        api = await authorize("api")
        assert (api.caller_identity, api.caller_admin) == ("api", True)

    asyncio.run(scenario())


def test_stopping_under_load_answers_every_request_it_was_sent(tmp_path):
    """As at an engine handover: the stopped primary's queue member leaves, and
    no request the broker routed to it is dropped. The race this guards against
    is timing-dependent, so this catches a regression only some of the time;
    ``test_stop_ends_delivery_at_the_broker_before_draining`` pins the order."""
    import nats
    import pytest
    from naas_abi_core.engine.nats_test_server import (
        native_nats_server,
        nats_server_binary,
    )
    from naas_abi_core.services.discovery.discovery_service import DiscoveryService
    from naas_abi_core.services.discovery.discovery_service_test import MemoryRegistry
    from nats.errors import TimeoutError as NATSTimeoutError

    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    subject = "abi.discovery.test.v1.list_modules"
    request = pb.ListModulesRequest().SerializeToString()

    async def stop_once(url: str) -> int:
        service = DiscoveryService(MemoryRegistry())
        old_nc, new_nc, client_nc = [await nats.connect(url) for _ in range(3)]
        old = DiscoveryNATS(service, SECRET, "test")
        new = DiscoveryNATS(service, SECRET, "test")
        await old.start(old_nc)
        await new.start(new_nc)
        lost, sending = [], asyncio.Event()
        sending.set()

        async def send():
            while sending.is_set():
                try:
                    await client_nc.request(subject, request, timeout=5)
                except NATSTimeoutError:
                    lost.append(1)

        senders = [asyncio.create_task(send()) for _ in range(64)]
        await asyncio.sleep(0.2)
        await old.stop()
        await asyncio.sleep(0.2)
        sending.clear()
        await asyncio.gather(*senders)
        await new.stop()
        for nc in (old_nc, new_nc, client_nc):
            await nc.close()
        return len(lost)

    async def scenario(url: str) -> list[int]:
        return [await stop_once(url) for _ in range(5)]

    with native_nats_server(tmp_path) as url:
        assert asyncio.run(scenario(url)) == [0] * 5


def test_stop_ends_delivery_at_the_broker_before_draining(monkeypatch):
    """``Subscription.drain`` alone can drop a request routed between its PING
    and its UNSUB, so the broker must confirm the UNSUBs first
    (``nats_sessions.stop_delivery``)."""
    from naas_abi_core.services.discovery.adapters.primary import discovery_nats

    calls: list[tuple[str, object]] = []

    async def stop_delivery(subscriptions):
        calls.append(("stop_delivery", list(subscriptions)))

    def subscription(name):
        async def drain():
            calls.append(("drain", name))

        return SimpleNamespace(name=name, drain=drain)

    monkeypatch.setattr(discovery_nats, "stop_delivery", stop_delivery, raising=False)
    primary = DiscoveryNATS(AsyncMock(), SECRET, "test")
    subscriptions = [subscription("a"), subscription("b")]
    primary.subscriptions = list(subscriptions)

    asyncio.run(primary.stop())

    assert calls == [
        ("stop_delivery", subscriptions),
        ("drain", "a"),
        ("drain", "b"),
    ]
    assert primary.subscriptions == []
