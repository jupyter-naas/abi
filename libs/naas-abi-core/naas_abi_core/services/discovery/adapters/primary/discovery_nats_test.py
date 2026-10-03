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
