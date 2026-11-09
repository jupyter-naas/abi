"""A module process stopped while a browser holds a stream of its app open.

SIGTERM must end the process within a container's grace period (Docker waits
10 s before SIGKILL), and the reader must see the stream end with an error,
not cleanly (remote apps ADR, amendment of 2026-10-14).
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import textwrap
import time

import nats
import pytest
from naas_abi_core.engine.nats_test_server import (
    native_nats_server,
    nats_server_binary,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.discovery.discovery_factory import start_discovery

SECRET = TEST_TOKENS.verifier
# Docker's default grace period, less a margin for a loaded test machine.
GRACE_SECONDS = 8.0
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        nats_server_binary() is None, reason="nats-server not installed"
    ),
]

MODULE = textwrap.dedent(
    """
    import asyncio
    import os
    import sys

    from naas_abi_sdk import BaseModule, DiscoveryConfiguration, run_module
    from naas_abi_sdk.apps import AppDescriptor


    async def events(scope, receive, send):
        if scope["type"] != "http":
            raise RuntimeError("no lifespan")
        start = {"type": "http.response.start", "status": 200, "headers": []}
        await send(start)
        await send({"type": "http.response.body", "body": b"data: 1\\n\\n", "more_body": True})
        await asyncio.Event().wait()  # an idle stream, as server-sent events are


    class Streamer(BaseModule):
        module_id = "acme.streamer"
        apps = (AppDescriptor("events", "Events"),)

        async def on_initialized(self):
            self.expose_app("events", events)

        async def run(self):
            while self.discovery_status != "READY":
                await asyncio.sleep(0.05)
            print("READY", flush=True)
            await asyncio.Event().wait()


    asyncio.run(
        run_module(
            Streamer,
            url=os.environ["NATS_URL"],
            token=os.environ["ABI_TOKEN"],
            discovery=DiscoveryConfiguration(),
        )
    )
    """
)


@pytest.fixture
def broker(tmp_path):
    with native_nats_server(tmp_path, jetstream=True) as url:
        yield url


def test_sigterm_with_a_stream_open_ends_the_module_and_fails_the_stream(
    broker, tmp_path
):
    url = broker
    from naas_abi_proto.app.v1 import app_pb2
    from naas_abi_sdk.app_host import call_app
    from naas_abi_sdk.app_streams import pull_body
    from naas_abi_sdk.credentials import host_audience
    from naas_abi_sdk.discovery import DiscoveryClient
    from naas_abi_sdk.transport import RPCError, Transport

    script = tmp_path / "streamer.py"
    script.write_text(MODULE)

    async def scenario():
        nc = await nats.connect(url)
        registry = await start_discovery(nc, SECRET)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script),
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join(sys.path),
                "NATS_URL": url,
                "ABI_TOKEN": TEST_TOKENS.token("acme.streamer"),
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        nexus = Transport(
            url,
            TEST_TOKENS.token("api"),
            timeout=10,
            host_token=lambda recipient: TEST_TOKENS.token(
                "api", audience=host_audience(recipient)
            ),
        )
        try:
            assert process.stdout is not None
            line = await asyncio.wait_for(process.stdout.readline(), 30)
            assert line.strip() == b"READY", line
            (instance,) = await DiscoveryClient(nexus).get_module("acme.streamer")
            answer = await call_app(
                nexus,
                "default",
                instance.instance_id,
                app_pb2.HttpRequest(app="events", method="GET", path="/stream"),
                service_account=instance.service_account,
            )
            assert answer.body_follows
            stream = pull_body(await nexus.connect(), answer.body_inbox)
            assert await stream.__anext__() == b"data: 1\n\n"
            reader = asyncio.create_task(stream.__anext__())  # waits for an event
            await asyncio.sleep(0.3)

            process.send_signal(signal.SIGTERM)
            started = time.monotonic()
            await asyncio.wait_for(process.wait(), GRACE_SECONDS)

            assert process.returncode == 0
            assert time.monotonic() - started < GRACE_SECONDS
            with pytest.raises(RPCError):  # an error, never a clean end
                await asyncio.wait_for(reader, 5)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            await nexus.close()
            await registry.stop()
            await nc.close()

    asyncio.run(scenario())
