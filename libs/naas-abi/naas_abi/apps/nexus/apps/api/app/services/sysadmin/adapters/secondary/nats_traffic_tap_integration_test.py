"""The traffic tap on a real nats-server: real micro services, real service tokens."""

import asyncio
import shutil
import socket
import subprocess
import time

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_traffic_tap import (
    NatsTrafficTap,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def broker(tmp_path):
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("nats-server is not installed")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [binary, "-a", "127.0.0.1", "-p", str(port), "-js", "-sd", str(tmp_path / "js")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.02)
        yield f"nats://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_the_tap_sees_calls_errors_and_events_but_not_transfers(broker):
    import nats
    from naas_abi_core.engine.nats_auth import issue_service_token
    from nats.micro import add_service
    from nats.micro.service import EndpointConfig, ServiceConfig

    seen = []

    async def scenario():
        server = await nats.connect(broker, name="abi-engine")
        caller = await nats.connect(broker, name="nexus-api")
        tap_connection = await nats.connect(broker, name="tap")

        async def ok(req):
            await req.respond(b"x" * 42)

        async def missing(req):
            await req.respond_error("404", "not found")

        service = await add_service(server, ServiceConfig(name="document", version="1.0.0"))
        await service.add_endpoint(
            EndpointConfig(name="get", subject="abi.svc.document.v1.get", handler=ok)
        )
        await service.add_endpoint(
            EndpointConfig(name="find", subject="abi.svc.document.v1.find", handler=missing)
        )
        transfer = await server.subscribe("abi.svc.object_storage.v1.transfer.read", cb=ok)

        async def connect():
            return tap_connection

        tap = NatsTrafficTap(connect)
        await tap.start(seen.append)
        await tap_connection.flush()
        headers = {"Nats-Auth-Token": issue_service_token("nexus-api", "s" * 48)}
        await caller.request("abi.svc.document.v1.get", b"q" * 7, timeout=2, headers=headers)
        await caller.request("abi.svc.document.v1.find", b"", timeout=2, headers=headers)
        await caller.request("abi.svc.object_storage.v1.transfer.read", b"", timeout=2)
        await caller.publish("evt.abc123.e-1", b"{}")
        await caller.flush()
        for _ in range(50):
            if len(seen) >= 3:
                break
            await asyncio.sleep(0.02)
        await tap.stop()
        await transfer.unsubscribe()
        await service.stop()
        for connection in (server, caller, tap_connection):
            await connection.close()

    asyncio.run(scenario())

    by_method = {(e.service, e.method): e for e in seen}
    assert set(by_method) == {("document", "get"), ("document", "find"), ("abc123", "publish")}
    get = by_method[("document", "get")]
    assert (get.caller, get.request_bytes, get.reply_bytes, get.status) == (
        "nexus-api",
        7,
        42,
        "ok",
    )
    assert get.latency_ms is not None and get.latency_ms >= 0
    assert (by_method[("document", "find")].status, by_method[("document", "find")].error_code) == (
        "error",
        "404",
    )
    assert by_method[("abc123", "publish")].status == "published"
