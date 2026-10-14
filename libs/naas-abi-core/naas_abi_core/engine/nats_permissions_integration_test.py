"""A broker as deployed: the engine logs in as ``abi``, modules as ``module``.

The module user's permissions (nats_permissions.MODULE_PERMISSIONS) keep it off the
engine's service and discovery subjects and its key-value buckets, and modules hold
keys of their own instead of the project secret. A module still registers, serves its
agents and apps, and calls other modules. Jobs and claim checks run as ``module`` in
the SDK's integration suites (tests/test_jobs_integration.py, test_claim_check.py).
"""

from __future__ import annotations

import asyncio
import json

import nats
import pytest
from naas_abi_core.engine.nats_auth import (
    issue_module_token,
    issue_service_token,
    module_key,
)
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
    pytest.mark.skipif(nats_server_binary() is None, reason="nats-server not installed"),
]


@pytest.fixture
def broker(tmp_path):
    with native_nats_server(tmp_path, jetstream=True, users=PASSWORDS) as url:
        yield login(url, "abi", PASSWORDS["abi"]), login(url, "module", PASSWORDS["module"])


def _module_token(module_id: str) -> str:
    return issue_module_token(module_id, module_key(SECRET, module_id))


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
    listen = ["abi.svc.document.v1.get", "abi.discovery.acme.v1.register", "$KV.abi.key"]
    write = ["$KV.abi.key", "$JS.API.STREAM.DELETE.ABI_JOBS_acme"]

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
                subscribe=["abi.mod.acme.i-1.app.console.http", "_INBOX.x"],
                publish=["abi.svc.document.v1.get", "abi.discovery.acme.v1.register"],
            )
        )
        == []
    )
    # The engine keeps every right.
    assert asyncio.run(_violations(engine, subscribe=listen, publish=write)) == []


def test_modules_register_and_serve_agents_and_apps_as_the_module_user(broker, tmp_path):
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
        documents = DocumentPrimaryAdapterNATS(DocumentService._for_engine(backend), SECRET)
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

        nexus = Transport(engine, issue_service_token("api", SECRET), timeout=10)
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
                app_pb2.HttpRequest(app="console", method="GET", path="/", user_id="u-1"),
            )
            assert answer.status == 200
            assert json.loads(answer.body) == {"user_id": "u-1", "caller": "api"}

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
