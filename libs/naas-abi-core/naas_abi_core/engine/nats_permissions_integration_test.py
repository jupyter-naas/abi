"""A broker as deployed: the engine logs in as ``abi``, modules as ``module``.

The module user's permissions (nats_permissions.MODULE_PERMISSIONS) keep it off the
engine's service and discovery subjects and replies, and out of stream creation and
key-value writes; modules hold keys of their own instead of the project secret, and
the tokens they are sent are bound to them. A module still registers, serves its
agents and apps, and calls other modules. Jobs and claim checks run as ``module`` in
the SDK's integration suites (tests/test_jobs_integration.py, test_claim_check.py).
"""

from __future__ import annotations

import asyncio
import json

import nats
import pytest
from naas_abi_core.engine.nats_auth import ServiceTokenSource, module_key
from naas_abi_core.engine.nats_test_server import (
    login,
    native_nats_server,
    nats_server_binary,
)
from naas_abi_core.services.discovery.discovery_factory import start_discovery

SECRET = "permissions-integration-test-secret-32-bytes"
PASSWORDS = {"abi": "nats-abi-integration", "module": "nats-module-integration"}
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        nats_server_binary() is None, reason="nats-server not installed"
    ),
]


@pytest.fixture
def broker(tmp_path):
    with native_nats_server(tmp_path, jetstream=True, users=PASSWORDS) as url:
        yield (
            login(url, "abi", PASSWORDS["abi"]),
            login(url, "module", PASSWORDS["module"]),
        )


def _module_token(module_id: str):
    from naas_abi_sdk.service_token import ModuleToken

    return ModuleToken(module_id, module_key(SECRET, module_id))


async def _violations(url: str, *, subscribe=(), publish=()) -> list[str]:
    """The permission errors the broker reports for these subscriptions and publishes."""
    errors: list[str] = []

    async def on_error(exc: Exception) -> None:
        errors.append(str(exc).lower())  # nats-py lowercases the server's -ERR

    nc = await nats.connect(url, error_cb=on_error, allow_reconnect=False)
    try:
        for subject in subscribe:
            await nc.subscribe(subject)
        for subject in publish:
            await nc.publish(subject, b"x")
        await nc.flush()
        await asyncio.sleep(0.2)
    finally:
        await nc.close()
    return errors


def test_a_module_cannot_listen_on_the_engine_nor_touch_its_buckets(broker):
    engine, module = broker
    listen = [
        "abi.svc.document.v1.get",
        "abi.discovery.acme.v1.register",
        "abi.rpc.overflow.open",
        "_INBOX.engine-replies",
        "$KV.abi.key",
    ]
    write = [
        "$KV.abi.key",
        # A stream on abi.svc.> would capture the engine's calls and their tokens.
        "$JS.API.STREAM.CREATE.CAPTURE",
        "$JS.API.STREAM.UPDATE.ABI_JOBS_acme",
        "$JS.API.STREAM.DELETE.ABI_JOBS_acme",
        "$JS.API.DIRECT.GET.KV_abi",
        # Deleting another module's durable job consumer would drop its triggers.
        "$JS.API.CONSUMER.DELETE.ABI_JOBS_acme.other",
    ]

    denied = asyncio.run(_violations(module, subscribe=listen, publish=write))

    for subject in listen + write:
        assert any(
            "permissions violation" in error and subject.lower() in error
            for error in denied
        ), (subject, denied)
    # What a module does: serve its own subjects, call services and discovery.
    assert (
        asyncio.run(
            _violations(
                module,
                subscribe=["abi.mod.acme.i-1.app.console.http", "_INBOX_MODULES.x"],
                publish=["abi.svc.document.v1.get", "abi.discovery.acme.v1.register"],
            )
        )
        == []
    )
    # The engine keeps every right.
    assert asyncio.run(_violations(engine, subscribe=listen, publish=write)) == []


def test_modules_register_and_serve_agents_and_apps_as_the_module_user(
    broker, tmp_path
):
    engine, module = broker
    from naas_abi_core.services.document.adapters.primary.document__primary_adapter__NATS import (
        DocumentPrimaryAdapterNATS,
    )
    from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
        DocumentSecondaryAdapterSQLite,
    )
    from naas_abi_core.services.document.DocumentService import DocumentService
    from naas_abi_proto.app.v1 import app_pb2
    from naas_abi_sdk import (
        AgentDescriptor,
        BaseModule,
        DiscoveryConfiguration,
        ModuleDependencies,
        run_module,
    )
    from naas_abi_sdk.app_host import call_app
    from naas_abi_sdk.apps import AppDescriptor
    from naas_abi_sdk.discovery import DiscoveryClient
    from naas_abi_sdk.transport import RPCError, Transport

    async def scenario():
        nc = await nats.connect(engine)
        registry = await start_discovery(nc, SECRET)
        backend = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
        documents = DocumentPrimaryAdapterNATS(
            DocumentService._for_engine(backend), SECRET
        )
        await documents.start(nc)
        stop = asyncio.Event()

        async def console(scope, receive, send):
            await receive()
            body = json.dumps(scope["abi"]).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": body})

        class Provider(BaseModule):
            module_id = "acme.provider"
            dependencies = ModuleDependencies(services=("document",))
            agents = (AgentDescriptor("Echo", capabilities=("agent.invoke.v1",)),)
            apps = (AppDescriptor("console", "Console"),)

            async def on_initialized(self):
                class Echo:
                    async def invoke(self, prompt, context):
                        return f"echo {prompt}"

                    async def stream_invoke(self, prompt, context):
                        yield {"event": "message", "data": f"echo {prompt}"}

                self.expose_agent("Echo", Echo())
                self.expose_app("console", console)

            async def run(self):
                await stop.wait()

        class Consumer(BaseModule):
            module_id = "acme.consumer"
            dependencies = ModuleDependencies(modules=("acme.provider",))

            async def run(self):
                agent = await self.engine.modules["acme.provider"].get_agent("Echo")
                return await agent.invoke("hi", timeout=10)

        nexus = Transport(engine, ServiceTokenSource("api", SECRET), timeout=10)
        provider = asyncio.create_task(
            run_module(
                Provider,
                url=module,
                token=_module_token("acme.provider"),
                discovery=DiscoveryConfiguration(),
            )
        )
        try:
            consumed = await asyncio.wait_for(
                run_module(
                    Consumer,
                    url=module,
                    token=_module_token("acme.consumer"),
                    discovery=DiscoveryConfiguration(refresh_seconds=0.05),
                ),
                30,
            )
            assert consumed == "echo hi"

            (instance,) = await DiscoveryClient(nexus).get_module("acme.provider")
            answer = await call_app(
                nexus,
                "default",
                instance.instance_id,
                app_pb2.HttpRequest(
                    app="console", method="GET", path="/", user_id="u-1"
                ),
            )
            assert answer.status == 200
            assert json.loads(answer.body) == {
                "user_id": "u-1",
                "workspace_id": "",
                "caller": "api",
            }

            # The token the provider was sent is bound to it: replayed to the
            # engine's services, it is refused (it would act as api there).
            sent = nexus.token.for_audience(instance.instance_id)
            replay = Transport(module, sent, timeout=10)
            try:
                with pytest.raises(RPCError, match="UNAUTHENTICATED"):
                    await DiscoveryClient(replay).evict(instance.instance_id)
            finally:
                await replay.close()

            # Another module may call the app, never on behalf of a user.
            peer = Transport(module, _module_token("acme.consumer"), timeout=10)
            try:
                with pytest.raises(RPCError, match="PERMISSION_DENIED"):
                    await call_app(
                        peer,
                        "default",
                        instance.instance_id,
                        app_pb2.HttpRequest(
                            app="console", method="GET", path="/", user_id="u-1"
                        ),
                    )
                # Nor register an instance whose id puts the provider's id where
                # callers read the audience: abi.mod.<p>.<provider>.x... .
                dotted = _register_request("acme.consumer")
                dotted.instance_id = f"{instance.instance_id}.x"
                with pytest.raises(RPCError, match="INVALID_ARGUMENT"):
                    await DiscoveryClient(peer)._call(
                        "register", dotted, _register_response()
                    )
                # Nor register under the provider's module id.
                with pytest.raises(RPCError, match="PERMISSION_DENIED"):
                    await DiscoveryClient(peer)._call(
                        "register",
                        _register_request("acme.provider"),
                        _register_response(),
                    )
            finally:
                await peer.close()
        finally:
            stop.set()
            await provider
            await nexus.close()
            await registry.stop()
            await documents.stop()
            await nc.close()
            backend.close()

    asyncio.run(scenario())


def _register_request(module_id: str):
    from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

    return pb.RegisterRequest(
        descriptor=pb.ModuleDescriptor(module_id=module_id, contract_major=1),
        instance_id="squatter",
        lease_token="s" * 32,
    )


def _register_response():
    from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

    return pb.RegisterResponse


def test_a_module_cannot_overhear_rpc_overflow_but_still_uploads_through_it(broker):
    """Overflow requests carry the caller's unbound token (an ``api`` upload from
    Nexus above the broker limit): a module listening there would get it."""
    engine, module = broker
    from naas_abi_core.engine.nats_overflow import OverflowHost
    from naas_abi_sdk import overflow
    from naas_abi_sdk.transport import Transport

    payload = b"x" * (3 * 64 * 1024)

    async def scenario():
        nc = await nats.connect(engine)
        host = OverflowHost(SECRET, chunk_bytes=64 * 1024)
        await host.start(nc)
        errors: list[str] = []
        overheard: list[bytes] = []

        async def on_error(exc: Exception) -> None:
            errors.append(str(exc).lower())

        async def overhear(msg) -> None:
            overheard.append(msg.data)

        spy = await nats.connect(
            module, error_cb=on_error, inbox_prefix="_INBOX_MODULES"
        )
        await spy.subscribe("abi.rpc.overflow.>", cb=overhear)
        await spy.flush()
        nexus = Transport(engine, ServiceTokenSource("api", SECRET), timeout=5)
        peer = Transport(module, _module_token("acme.consumer"), timeout=5)
        try:
            for client in (nexus, peer):  # a module's own upload still goes through
                transfer_id = await overflow.upload(
                    client.call, payload, chunk_bytes=64 * 1024
                )
                await overflow.close(client.call, transfer_id)
            await spy.flush()
            await asyncio.sleep(0.2)
        finally:
            await nexus.close()
            await peer.close()
            await spy.close()
            await host.stop()
            await nc.close()
        return errors, overheard

    errors, overheard = asyncio.run(scenario())

    assert overheard == []
    assert any(
        "permissions violation" in e and "abi.rpc.overflow.>" in e for e in errors
    ), errors


def test_a_module_cannot_overhear_the_engines_jetstream_requests(broker):
    """A module subscribed to $JS.API.> would see the engine's reads of discovery's
    registry, reply subject included, and could race a forged reply."""
    engine, module = broker
    from naas_abi_sdk.discovery import DiscoveryClient
    from naas_abi_sdk.transport import Transport

    async def scenario():
        nc = await nats.connect(engine)
        registry = await start_discovery(nc, SECRET)
        errors: list[str] = []
        overheard: list[str] = []

        async def on_error(exc: Exception) -> None:
            errors.append(str(exc).lower())

        async def overhear(msg) -> None:
            overheard.append(msg.subject)

        spy = await nats.connect(
            module, error_cb=on_error, inbox_prefix="_INBOX_MODULES"
        )
        for subject in ("$JS.API.>", "$JS.EVENT.>", "$JS.ACK.>"):
            await spy.subscribe(subject, cb=overhear)
        await spy.flush()
        peer = Transport(module, _module_token("acme.consumer"), timeout=5)
        try:
            # Each call reads the registry: a JetStream message get by the engine.
            for _ in range(3):
                await DiscoveryClient(peer).list_modules()
            await spy.flush()
            await asyncio.sleep(0.2)
        finally:
            await peer.close()
            await spy.close()
            await registry.stop()
            await nc.close()
        return errors, overheard

    errors, overheard = asyncio.run(scenario())

    assert overheard == []
    for subject in ("$js.api.>", "$js.event.>", "$js.ack.>"):
        assert any("permissions violation" in e and subject in e for e in errors), (
            errors
        )
