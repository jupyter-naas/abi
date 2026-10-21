"""NATS adapters against a real nats-server with JetStream and HTTP monitoring."""

import asyncio
import shutil
import socket
import subprocess
import time

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_http_monitor import (
    NatsHttpMonitor,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_micro import (
    NatsMicroServiceMonitor,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    MicroServiceMonitorContract,
    NatsServerMonitorContract,
)

pytestmark = pytest.mark.integration


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for(port):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    pytest.fail(f"port {port} never opened")


class Deployment:
    """The contracts' deployment, on a real broker, driven from one background loop."""

    def __init__(self, url):
        self.url = url
        self.loop = asyncio.new_event_loop()

    def run(self, coro):
        return self.loop.run_until_complete(coro)

    async def start(self):
        import nats
        from nats.js.api import ConsumerConfig, StreamConfig
        from nats.micro import add_service
        from nats.micro.service import EndpointConfig, ServiceConfig

        self.api = await nats.connect(self.url, name="api")
        self.other = await nats.connect(self.url)

        async def ok(req):
            await req.respond(b"ok")

        self.services = []
        for name, subjects in (("document", ["a"]), ("document", ["b"]), ("keyvalue", ["get"])):
            service = await add_service(self.api, ServiceConfig(name=name, version="1.0.0"))
            for subject in subjects:
                await service.add_endpoint(
                    EndpointConfig(name=subject, subject=f"abi.svc.{name}.v1.{subject}", handler=ok)
                )
            self.services.append(service)
        for subject, times in (("abi.svc.document.v1.a", 3), ("abi.svc.document.v1.b", 2)):
            for _ in range(times):
                await self.api.request(subject, b"", timeout=2)

        js = self.api.jetstream()
        kv = await js.create_key_value(bucket="ABI_DISCOVERY_zen")
        await kv.put("registry", b"{}")
        await js.add_stream(StreamConfig(name="ABI_JOBS_zen", subjects=["abi.jobs.zen.>"]))
        for subject in (
            "abi.jobs.zen.schedule.x.y.0",
            "abi.jobs.zen.schedule.x.y.1",
            "abi.jobs.zen.cancel.x",
            "abi.jobs.zen.trigger.a.b",
        ):
            await js.publish(subject, b"{}")
        await js.add_consumer(
            "ABI_JOBS_zen",
            ConsumerConfig(durable_name="job-a-b", filter_subject="abi.jobs.zen.trigger.a.b"),
        )

    async def stop(self):
        for service in self.services:
            await service.stop()
        await self.other.close()
        await self.api.close()


@pytest.fixture(scope="module")
def deployment(tmp_path_factory):
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("nats-server is not installed")
    port, monitoring = _port(), _port()
    process = subprocess.Popen(
        [
            binary,
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
            "-m",
            str(monitoring),
            "-js",
            "-sd",
            str(tmp_path_factory.mktemp("js")),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(port)
        _wait_for(monitoring)
        deployment = Deployment(f"nats://127.0.0.1:{port}")
        deployment.monitoring_url = f"http://127.0.0.1:{monitoring}"
        deployment.run(deployment.start())
        yield deployment
        deployment.run(deployment.stop())
        deployment.loop.close()
    finally:
        process.terminate()
        process.wait(timeout=5)


class _OnLoop:
    """Runs an async adapter on the deployment loop (contracts call asyncio.run)."""

    def __init__(self, deployment, adapter):
        self._deployment, self._adapter = deployment, adapter

    def __getattr__(self, name):
        method = getattr(self._adapter, name)

        def call(*args, **kwargs):
            result = self._deployment.run(method(*args, **kwargs))

            async def done():
                return result

            return done()

        return call


@pytest.fixture
def monitor(request, deployment):
    if "Server" in request.cls.__name__:
        return NatsHttpMonitor(deployment.monitoring_url)

    async def connect():
        return deployment.api

    return _OnLoop(deployment, NatsMicroServiceMonitor(connect))


class TestRealMicroServices(MicroServiceMonitorContract):
    pass


class TestRealServerMonitor(NatsServerMonitorContract):
    pass
