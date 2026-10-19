import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from naas_abi_core.engine.nats_auth import HOST_AUDIENCE
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.discovery.adapters.primary.discovery_nats import (
    DiscoveryNATS,
)
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

SECRET = TEST_TOKENS.verifier


def test_authentication_precedes_domain_mutations_and_binds_caller():
    async def scenario():
        service = AsyncMock()
        primary = DiscoveryNATS(service, TEST_TOKENS.verifier, "test")
        service.register.return_value = pb.RegisterResponse()
        msg = SimpleNamespace(
            data=pb.RegisterRequest().SerializeToString(),
            headers={},
            reply="_INBOX.reply",
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
        msg.headers = {"Nats-Auth-Token": TEST_TOKENS.token("caller")}
        await primary._handle("register", msg)
        assert service.register.call_args.args[1] == "caller"

    asyncio.run(scenario())


def test_evict_is_an_authenticated_mutation_decided_by_iam():
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.discovery.adapters.primary.discovery_nats import (
        OPERATIONS,
    )
    from naas_abi_core.services.discovery.discovery_service import DiscoveryService
    from naas_abi_core.services.discovery.discovery_service_test import (
        MemoryRegistry,
        registration,
    )
    from naas_abi_core.services.iam.tests.authorization_contract import (
        contract_iam,
    )
    from naas_abi_core.services.iam.tests.iam_harness import IAMHarness

    async def scenario():
        iam = contract_iam()
        # Recorded, holding no policy: it may not evict, nor see the module.
        IAMHarness(iam).service_account("research")
        service = DiscoveryService(MemoryRegistry(), project="test", iam=iam)
        with as_service_account("engine"):
            await service.register(registration("research", "r-1"), "research")
        primary = DiscoveryNATS(service, TEST_TOKENS.verifier, "test")

        async def evict_as(identity):
            msg = SimpleNamespace(
                data=pb.EvictRequest(instance_id="r-1").SerializeToString(),
                headers={"Nats-Auth-Token": TEST_TOKENS.token(identity)},
                reply="_INBOX.reply",
                respond=AsyncMock(),
                _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
            )
            await primary._handle("evict", msg)
            return pb.EvictResponse.FromString(msg._client.publish.call_args.args[1])

        assert OPERATIONS["evict"][2] is True
        assert (await evict_as("research")).error.code == "INSTANCE_NOT_FOUND"
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
        primary = DiscoveryNATS(service, TEST_TOKENS.verifier, "test")
        msg = SimpleNamespace(
            data=b"",
            headers={
                "Nats-Auth-Token": TEST_TOKENS.token("caller"),
                "Abi-Overflow-Request": f"{'a' * 32}:upload",
            },
            reply="_INBOX.reply",
            _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
        )
        await primary._handle("register", msg)
        response = pb.RegisterResponse.FromString(msg._client.publish.call_args.args[1])
        assert response.error.code == "PAYLOAD_TOO_LARGE"
        service.register.assert_not_awaited()

    asyncio.run(scenario())


def test_authorize_agent_verifies_the_forwarded_caller_and_its_user():
    async def scenario():
        service = AsyncMock()
        service.authorize_agent.return_value = pb.AuthorizeAgentResponse()
        primary = DiscoveryNATS(service, TEST_TOKENS.verifier, "test")

        async def authorize(caller, on_behalf_of="", audience=HOST_AUDIENCE):
            msg = SimpleNamespace(
                data=pb.AuthorizeAgentRequest(
                    instance_id="r-1",
                    agent_name="Researcher",
                    caller_token=TEST_TOKENS.token(caller, audience=audience),
                    caller_on_behalf_of=on_behalf_of,
                ).SerializeToString(),
                headers={"Nats-Auth-Token": TEST_TOKENS.token("research")},
                reply="_INBOX.reply",
                _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
            )
            await primary._handle("authorize_agent", msg)
            return pb.AuthorizeAgentResponse.FromString(
                msg._client.publish.call_args.args[1]
            )

        await authorize("orchestrator")
        _, owner, caller = service.authorize_agent.call_args.args
        assert (owner, caller.principal.id, caller.on_behalf_of) == (
            "research",
            "orchestrator",
            None,
        )
        await authorize("api", "user-1")
        caller = service.authorize_agent.call_args.args[2]
        assert (caller.principal.id, caller.user.id) == ("api", "user-1")
        # Only a trusted identity names the user it acts for.
        refused = await authorize("orchestrator", "user-1")
        assert refused.error.code == "UNAUTHENTICATED"
        assert service.authorize_agent.await_count == 2
        # A host holds a token addressed to hosts, never the caller's own: the
        # kernel's token (``abi:nats``) is refused here, so a host handed one
        # would be refused too, and a host token buys nothing at any kernel
        # service (they accept ``abi:nats`` only).
        own = await authorize("api", "user-1", audience="abi:nats")
        assert own.error.code == "UNAUTHENTICATED"
        assert service.authorize_agent.await_count == 2

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
        old = DiscoveryNATS(service, TEST_TOKENS.verifier, "test")
        new = DiscoveryNATS(service, TEST_TOKENS.verifier, "test")
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
    primary = DiscoveryNATS(AsyncMock(), TEST_TOKENS.verifier, "test")
    subscriptions = [subscription("a"), subscription("b")]
    primary.subscriptions = list(subscriptions)

    asyncio.run(primary.stop())

    assert calls == [
        ("stop_delivery", subscriptions),
        ("drain", "a"),
        ("drain", "b"),
    ]
    assert primary.subscriptions == []


class _Subscriber:
    """A NATS connection that records the callbacks it is given."""

    max_payload = 1024 * 1024

    def __init__(self):
        self.callbacks = {}

    async def subscribe(self, subject, queue="", cb=None):
        self.callbacks[subject.rsplit(".", 1)[-1]] = cb
        return SimpleNamespace(
            unsubscribe=AsyncMock(), drain=AsyncMock(), _id=len(self.callbacks)
        )

    async def flush(self):
        pass


def _lookup_message():
    return SimpleNamespace(
        data=pb.GetModuleRequest(module_id="research").SerializeToString(),
        headers={"Nats-Auth-Token": TEST_TOKENS.token("caller")},
        reply="_INBOX.reply",
        subject="abi.discovery.test.v1.get_module",
        _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
    )


def test_lookups_are_answered_side_by_side_and_stop_waits_for_them(monkeypatch):
    from naas_abi_core.services.discovery.adapters.primary import discovery_nats

    monkeypatch.setattr(discovery_nats, "stop_delivery", AsyncMock())

    async def scenario():
        release = asyncio.Event()
        running = []

        async def get_module(request):
            running.append(request.module_id)
            await release.wait()
            return pb.GetModuleResponse()

        service = SimpleNamespace(get_module=get_module)
        primary = DiscoveryNATS(service, TEST_TOKENS.verifier, "test")
        nc = _Subscriber()
        await primary.start(nc)
        messages = [_lookup_message() for _ in range(3)]
        for msg in messages:
            await nc.callbacks["get_module"](msg)  # returns at once
        for _ in range(100):
            if len(running) == 3:
                break
            await asyncio.sleep(0.01)
        assert len(running) == 3  # one at a time would leave two waiting
        stopping = asyncio.create_task(primary.stop())
        await asyncio.sleep(0.05)
        assert not stopping.done()  # the calls received are answered first
        release.set()
        await asyncio.wait_for(stopping, timeout=2)
        return messages

    messages = asyncio.run(scenario())

    assert all(msg._client.publish.await_count == 1 for msg in messages)
