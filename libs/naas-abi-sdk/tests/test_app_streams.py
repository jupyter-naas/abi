"""Streamed app bodies against a real nats-server (its default 1 MB max_payload).

Plays Nexus: holds request bodies (BodySource) and pulls response bodies
(pull_body), as services/apps/remote does.
"""

import asyncio
import hashlib
import json
import shutil
import socket
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.app.v1 import app_pb2 as pb
from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb

from naas_abi_sdk import app_streams
from naas_abi_sdk.app_host import AppHost, call_app
from naas_abi_sdk.app_streams import BodySource, pull_body, rechunk
from naas_abi_sdk.apps import read_app
from naas_abi_sdk.transport import RPCError, Transport

pytestmark = pytest.mark.skipif(
    shutil.which("nats-server") is None, reason="nats-server not installed"
)
fastapi = pytest.importorskip("fastapi")
from fastapi.responses import StreamingResponse

MB = 1024 * 1024


@pytest.fixture
def broker(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    process = subprocess.Popen(
        ["nats-server", "-a", "127.0.0.1", "-p", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.05)
    yield f"nats://127.0.0.1:{port}"
    process.terminate()
    process.wait(timeout=5)


@pytest.fixture(autouse=True)
def fast_keepalive(monkeypatch):
    monkeypatch.setattr(app_streams, "KEEPALIVE_SECONDS", 0.3)
    monkeypatch.setattr(app_streams, "LINGER_SECONDS", 0.2)


def _app():
    api = fastapi.FastAPI()
    seen = SimpleNamespace(cancelled=False, events=0)

    @api.put("/api/upload")
    async def upload(request: fastapi.Request):
        digest, size = hashlib.sha256(), 0
        async for chunk in request.stream():
            digest.update(chunk)
            size += len(chunk)
        return {"size": size, "sha256": digest.hexdigest()}

    @api.get("/api/download")
    async def download(size: int):
        async def body():
            for _ in range(size // MB):
                yield b"d" * MB

        return StreamingResponse(body(), media_type="application/octet-stream")

    @api.get("/api/events")
    async def events():
        async def body():
            try:
                while True:
                    seen.events += 1
                    yield f"data: {seen.events}\n\n".encode()
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                seen.cancelled = True
                raise

        return StreamingResponse(body(), media_type="text/event-stream")

    @api.get("/api/stall")
    async def stall():
        await asyncio.sleep(3600)

    return api, seen


async def _module(url, tmp_path, app, **kwargs):
    folder = tmp_path / "apps" / "console"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({"name": "Console"}))
    (folder / "big.js").write_bytes(b"j" * (3 * MB + 17))
    transport = Transport(url, "module-token")
    session = SimpleNamespace(
        instance_id="i-1",
        service_account="sa1",
        lease_token="l" * 32,
        client=SimpleNamespace(
            transport=transport,
            project="acme",
            _call=AsyncMock(
                return_value=discovery_pb.AuthorizeAppResponse(caller_identity="api")
            ),
        ),
    )
    host = AppHost(session, {"console": (read_app(folder), app)}, **kwargs)
    await host.start()
    return host


def _request(path, method="GET", **fields):
    return pb.HttpRequest(
        app="console",
        method=method,
        path=path,
        root_path="/app-html/remote/m/console",
        **fields,
    )


async def _body(nexus, response):
    if not response.body_follows:
        return response.body
    nc = await nexus.connect()
    return b"".join([chunk async for chunk in pull_body(nc, response.body_inbox)])


def test_a_large_upload_streams_through_the_app(broker, tmp_path):
    async def scenario():
        api, _ = _app()
        host = await _module(broker, tmp_path, api)
        nexus = Transport(
            broker, "nexus-token", timeout=60, host_token="nexus-host-token"
        )
        try:
            payload = bytes(range(256)) * (20 * MB // 256)  # 20 MB
            source = BodySource(await nexus.connect())
            await source.start()

            async def produce():
                pieces = (
                    payload[i : i + 64 * 1024]
                    for i in range(0, len(payload), 64 * 1024)
                )

                async def browser():
                    for piece in pieces:
                        yield piece

                async for chunk in rechunk(browser(), app_streams.chunk_bytes(1 * MB)):
                    await source.put(chunk)
                await source.finish()

            producer = asyncio.create_task(produce())
            response = await call_app(
                nexus,
                "acme",
                "i-1",
                _request(
                    "/api/upload",
                    "PUT",
                    body_follows=True,
                    body_inbox=source.inbox,
                    max_body_bytes=100 * MB,
                ),
                service_account="sa1",
            )
            await producer
            await source.close()
            assert response.status == 200, response
            assert json.loads(response.body) == {
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_an_upload_above_its_limit_is_413(broker, tmp_path):
    async def scenario():
        api, _ = _app()
        host = await _module(broker, tmp_path, api)
        nexus = Transport(
            broker, "nexus-token", timeout=60, host_token="nexus-host-token"
        )
        try:
            source = BodySource(await nexus.connect())
            await source.start()

            async def produce():
                for _ in range(8):
                    await source.put(b"x" * (256 * 1024))
                await source.finish()

            producer = asyncio.create_task(produce())
            response = await call_app(
                nexus,
                "acme",
                "i-1",
                _request(
                    "/api/upload",
                    "PUT",
                    body_follows=True,
                    body_inbox=source.inbox,
                    max_body_bytes=MB,
                ),
                service_account="sa1",
            )
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
            await source.close()
            assert response.status == 413
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_a_large_download_and_a_large_file_stream_back(broker, tmp_path):
    async def scenario():
        api, _ = _app()
        host = await _module(broker, tmp_path, api)
        nexus = Transport(
            broker, "nexus-token", timeout=60, host_token="nexus-host-token"
        )
        try:
            download = await call_app(
                nexus,
                "acme",
                "i-1",
                _request("/api/download", query=f"size={5 * MB}"),
                service_account="sa1",
            )
            assert download.status == 200 and download.body_follows
            assert await _body(nexus, download) == b"d" * (5 * MB)
            static = await call_app(
                nexus, "acme", "i-1", _request("/big.js"), service_account="sa1"
            )
            assert static.body_follows
            assert await _body(nexus, static) == b"j" * (3 * MB + 17)
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_leaving_an_endless_stream_stops_the_app(broker, tmp_path):
    async def scenario():
        api, seen = _app()
        host = await _module(broker, tmp_path, api)
        nexus = Transport(
            broker, "nexus-token", timeout=60, host_token="nexus-host-token"
        )
        try:
            response = await call_app(
                nexus, "acme", "i-1", _request("/api/events"), service_account="sa1"
            )
            assert response.body_follows
            stream = pull_body(await nexus.connect(), response.body_inbox)
            assert await stream.__anext__() == b"data: 1\n\n"
            assert await stream.__anext__() == b"data: 2\n\n"  # across keepalives
            await stream.aclose()  # the browser left: tells the module
            for _ in range(50):
                if seen.cancelled:
                    break
                await asyncio.sleep(0.1)
            assert seen.cancelled
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_an_idle_app_is_504(broker, tmp_path):
    async def scenario():
        api, _ = _app()
        host = await _module(broker, tmp_path, api, idle_seconds=0.5)
        nexus = Transport(
            broker, "nexus-token", timeout=60, host_token="nexus-host-token"
        )
        try:
            response = await call_app(
                nexus, "acme", "i-1", _request("/api/stall"), service_account="sa1"
            )
            assert response.status == 504
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_a_holder_that_stops_answering_fails_the_pull(broker):
    async def scenario():
        nexus = Transport(
            broker, "nexus-token", timeout=60, host_token="nexus-host-token"
        )
        try:
            nc = await nexus.connect()
            inbox = nc.new_inbox()

            async def ignore(msg):  # never answers
                pass

            await nc.subscribe(inbox, cb=ignore)
            with pytest.raises(RPCError, match="DEADLINE_EXCEEDED"):
                async for _ in pull_body(nc, inbox, timeout=0.2):
                    pass
        finally:
            await nexus.close()

    asyncio.run(scenario())
