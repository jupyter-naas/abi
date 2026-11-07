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

from naas_abi_sdk import app_host, app_streams
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


def _nexus(url, timeout=60):
    return Transport(
        url,
        "nexus-token",
        timeout=timeout,
        host_token=lambda recipient: "nexus-host-token",
    )


def _start_broker(tmp_path, *config_lines):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    command = ["nats-server", "-a", "127.0.0.1", "-p", str(port)]
    if config_lines:
        config = tmp_path / "nats.conf"
        config.write_text("\n".join(config_lines) + "\n")
        command += ["-c", str(config)]
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.05)
    return process, f"nats://127.0.0.1:{port}"


@pytest.fixture
def small_broker(tmp_path):
    """A broker whose messages hold 64 KiB, under the 256 KiB inline bodies."""
    process, url = _start_broker(tmp_path, "max_payload: 65536")
    yield url
    process.terminate()
    process.wait(timeout=5)


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

    @api.get("/api/quiet")
    async def quiet():
        """Server-sent events with one event, then nothing for a long time."""

        async def body():
            try:
                yield b"data: hello\n\n"
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                seen.cancelled = True
                raise

        return StreamingResponse(body(), media_type="text/event-stream")

    @api.get("/api/broken")
    async def broken():
        async def body():
            yield b"b" * MB
            raise RuntimeError("the disk went away")

        return StreamingResponse(body(), media_type="application/octet-stream")

    @api.get("/api/whole")
    async def whole(size: int):
        return fastapi.Response(b"w" * size, media_type="application/octet-stream")

    @api.get("/api/headers")
    async def headers():
        """A body under the inline size whose headers fill the message."""
        return fastapi.Response(
            b"h" * 40960, headers={"x-padding": "p" * 30000}, media_type="text/plain"
        )

    @api.get("/api/ping")
    async def ping():
        return {"pong": True}

    return api, seen


async def _module(url, tmp_path, app, manifest=None, **kwargs):
    folder = tmp_path / "apps" / "console"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps(manifest or {"name": "Console"}))
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
            broker,
            "nexus-token",
            timeout=60,
            host_token=lambda recipient: "nexus-host-token",
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
            broker,
            "nexus-token",
            timeout=60,
            host_token=lambda recipient: "nexus-host-token",
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
            broker,
            "nexus-token",
            timeout=60,
            host_token=lambda recipient: "nexus-host-token",
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
            broker,
            "nexus-token",
            timeout=60,
            host_token=lambda recipient: "nexus-host-token",
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
            broker,
            "nexus-token",
            timeout=60,
            host_token=lambda recipient: "nexus-host-token",
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
            broker,
            "nexus-token",
            timeout=60,
            host_token=lambda recipient: "nexus-host-token",
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


# -- review findings of 2026-10-13 (A5, A6, A9, A11, A12, A21, A22) ------------------


async def _upload(nexus, size, *, max_body_bytes=0, gate=None):
    """Start a PUT of ``size`` bytes; ``gate`` holds its last chunk back."""
    source = BodySource(await nexus.connect())
    await source.start()

    async def produce():
        sent = 0
        while sent < size:
            piece = min(256 * 1024, size - sent)
            if gate is not None and sent + piece >= size:
                await gate.wait()
            await source.put(b"u" * piece)
            sent += piece
        await source.finish()

    producer = asyncio.create_task(produce())
    call = asyncio.create_task(
        call_app(
            nexus,
            "acme",
            "i-1",
            _request(
                "/api/upload",
                "PUT",
                body_follows=True,
                body_inbox=source.inbox,
                max_body_bytes=max_body_bytes,
            ),
            service_account="sa1",
        )
    )
    return source, producer, call


def test_closing_ends_an_open_stream_with_an_error(broker, tmp_path):
    """A5: SIGTERM with a browser reading server-sent events: the host closes
    within its bound, and the reader sees an error, not a clean end."""

    async def scenario():
        api, _ = _app()
        host = await _module(broker, tmp_path, api)
        nexus = _nexus(broker, 60)
        try:
            events = await call_app(
                nexus, "acme", "i-1", _request("/api/events"), service_account="sa1"
            )
            quiet = await call_app(
                nexus, "acme", "i-1", _request("/api/quiet"), service_account="sa1"
            )
            nc = await nexus.connect()

            async def read(response):
                async for _ in pull_body(nc, response.body_inbox):
                    pass

            readers = [asyncio.create_task(read(r)) for r in (events, quiet)]
            await asyncio.sleep(0.8)
            started = time.monotonic()
            await asyncio.wait_for(host.close(), app_host.CLOSE_SECONDS + 2)
            assert time.monotonic() - started < app_host.CLOSE_SECONDS + 1
            for reader in readers:
                with pytest.raises(RPCError) as raised:
                    await asyncio.wait_for(reader, 5)
                assert raised.value.code == "MODULE_UNAVAILABLE"
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_draining_ends_event_streams_and_lets_a_download_finish(broker, tmp_path):
    """SIGTERM drains: server-sent events, which never end, end with an error
    at once (their readers reconnect elsewhere); a download in progress is
    read to its end. The drain is over long before its timeout."""

    async def scenario():
        api, seen = _app()
        host = await _module(broker, tmp_path, api)
        nexus = _nexus(broker, 60)
        try:
            events = await call_app(
                nexus, "acme", "i-1", _request("/api/events"), service_account="sa1"
            )
            quiet = await call_app(
                nexus, "acme", "i-1", _request("/api/quiet"), service_account="sa1"
            )
            download = await call_app(
                nexus,
                "acme",
                "i-1",
                _request("/api/download", query=f"size={8 * MB}"),
                service_account="sa1",
            )
            nc = await nexus.connect()

            async def read(response):
                return b"".join([c async for c in pull_body(nc, response.body_inbox)])

            readers = [asyncio.create_task(read(r)) for r in (events, quiet)]
            downloaded = asyncio.create_task(read(download))
            await asyncio.sleep(0.8)
            started = time.monotonic()
            await asyncio.wait_for(host.drain(30), app_host.CLOSE_SECONDS + 10)
            assert time.monotonic() - started < app_host.CLOSE_SECONDS + 5
            for reader in readers:
                with pytest.raises(RPCError) as raised:
                    await asyncio.wait_for(reader, 5)
                assert raised.value.code == "MODULE_UNAVAILABLE"
            assert seen.cancelled
            assert len(await asyncio.wait_for(downloaded, 10)) == 8 * MB
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_draining_lets_a_background_task_finish_after_its_stream(broker, tmp_path):
    """A streamed response whose body ended runs its Starlette background task
    (an audit write, an email): a drain waits for it, quiet as it is, and
    never cancels it."""
    from starlette.background import BackgroundTask

    api = fastapi.FastAPI()
    done = asyncio.Event()

    async def audit():
        await asyncio.sleep(app_host.DRAIN_IDLE_SECONDS * 2)
        done.set()

    @api.get("/api/export")
    async def export():
        async def body():
            yield b"e" * MB

        return StreamingResponse(
            body(),
            media_type="application/octet-stream",
            background=BackgroundTask(audit),
        )

    async def scenario():
        host = await _module(broker, tmp_path, api)
        nexus = _nexus(broker, 60)
        try:
            response = await call_app(
                nexus, "acme", "i-1", _request("/api/export"), service_account="sa1"
            )
            assert len(await _body(nexus, response)) == MB
            await asyncio.sleep(0.1)  # the body is over; the task runs
            await asyncio.wait_for(host.drain(30), 10)
            assert done.is_set()
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_an_app_failing_mid_stream_is_an_error_to_the_reader(broker, tmp_path):
    """A6, the module's half: the reader learns the body is cut."""

    async def scenario():
        api, _ = _app()
        host = await _module(broker, tmp_path, api)
        nexus = _nexus(broker, 60)
        try:
            response = await call_app(
                nexus, "acme", "i-1", _request("/api/broken"), service_account="sa1"
            )
            assert response.status == 200 and response.body_follows
            received = 0
            with pytest.raises(RPCError) as raised:
                async for chunk in pull_body(
                    await nexus.connect(), response.body_inbox
                ):
                    received += len(chunk)
            assert raised.value.code == "APP_ERROR"
            assert received == MB
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_a_body_too_large_for_one_message_streams(small_broker, tmp_path):
    """A9: under a 64 KiB broker limit, a 100 KiB answer (inline size for a
    1 MB broker) streams instead of failing to send."""

    async def scenario():
        api, _ = _app()
        host = await _module(small_broker, tmp_path, api)
        nexus = _nexus(small_broker, 10)
        try:
            whole = await call_app(
                nexus,
                "acme",
                "i-1",
                _request("/api/whole", query="size=102400"),
                service_account="sa1",
            )
            assert whole.status == 200 and whole.body_follows
            assert await _body(nexus, whole) == b"w" * 102400
            small = await call_app(
                nexus,
                "acme",
                "i-1",
                _request("/api/whole", query="size=1000"),
                service_account="sa1",
            )
            assert small.body == b"w" * 1000 and not small.body_follows
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_slow_uploads_hold_slots_of_their_own(broker, tmp_path):
    """A11: with every upload slot taken by a slow upload, other requests are
    answered, and one more upload is refused at once."""

    async def scenario():
        api, _ = _app()
        host = await _module(broker, tmp_path, api, max_concurrency=1, max_uploads=1)
        nexus = _nexus(broker, 60)
        quick = _nexus(broker, 2)
        gate = asyncio.Event()
        try:
            source, producer, upload = await _upload(nexus, 2 * MB, gate=gate)
            await asyncio.sleep(0.5)  # the app reads it, slowly
            assert not upload.done()
            ping = await call_app(
                quick, "acme", "i-1", _request("/api/ping"), service_account="sa1"
            )
            assert (ping.status, json.loads(ping.body)) == (200, {"pong": True})
            other, other_producer, refused = await _upload(quick, 2 * MB)
            with pytest.raises(RPCError) as raised:
                await refused
            assert raised.value.code == "MODULE_UNAVAILABLE"
            other_producer.cancel()
            await other.close()
            gate.set()
            response = await upload
            assert response.status == 200
            assert json.loads(response.body)["size"] == 2 * MB
            await producer
            await source.close()
        finally:
            await host.close()
            await nexus.close()
            await quick.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_the_apps_own_upload_limit_holds_whatever_the_request_says(broker, tmp_path):
    """A12: a request asking for no limit (0) still stops at the manifest's."""

    async def scenario():
        api, _ = _app()
        host = await _module(
            broker,
            tmp_path,
            api,
            manifest={"name": "Console", "max_upload_bytes": MB},
        )
        nexus = _nexus(broker, 60)
        try:
            source, producer, upload = await _upload(nexus, 2 * MB, max_body_bytes=0)
            response = await upload
            assert response.status == 413
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
            await source.close()
            fits, fits_producer, fits_upload = await _upload(nexus, MB)
            assert (await fits_upload).status == 200
            await fits_producer
            await fits.close()
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_a_lost_last_reply_is_answered_again(broker, monkeypatch):
    """A21: the reader asks for the last chunk again after its pull timeout;
    the holder still answers (it lingers past that timeout)."""
    monkeypatch.setattr(app_streams, "LINGER_SECONDS", 1.0)

    async def scenario():
        nexus = _nexus(broker, 60)
        try:
            nc = await nexus.connect()
            source = BodySource(nc)
            await source.start()
            await source.put(b"only")
            finish = asyncio.create_task(source.finish())
            first = pb.BodyChunk.FromString(
                (
                    await nc.request(
                        source.inbox,
                        pb.BodyPull(sequence=0).SerializeToString(),
                        timeout=2,
                    )
                ).data
            )
            assert first.data == b"only"
            await finish
            last = pb.BodyPull(sequence=1).SerializeToString()
            await nc.request(source.inbox, last, timeout=2)  # its reply "lost"
            await asyncio.sleep(0.5)  # the reader's timeout, scaled down
            again = pb.BodyChunk.FromString(
                (await nc.request(source.inbox, last, timeout=2)).data
            )
            assert again.last and again.sequence == 1
            await source.close()
        finally:
            await nexus.close()

    asyncio.run(scenario())


def test_a_finished_stream_lingers_without_holding_a_slot(broker, tmp_path):
    """A21: the linger outlasts the reader's pull timeout, so a finished body
    must not count against MAX_STREAMS while it lingers."""

    async def scenario():
        api, _ = _app()
        host = await _module(broker, tmp_path, api)
        nexus = _nexus(broker, 60)
        try:
            response = await call_app(
                nexus, "acme", "i-1", _request("/big.js"), service_account="sa1"
            )
            assert len(await _body(nexus, response)) == 3 * MB + 17
            for _ in range(20):
                if not host._streams:
                    break
                await asyncio.sleep(0.05)
            assert not host._streams
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_leaving_an_idle_stream_stops_the_app_at_once(broker, tmp_path, monkeypatch):
    """A22: the browser leaves while the stream is quiet and a pull waits for
    the next event: the app stops now, not after the keepalive."""
    monkeypatch.setattr(app_streams, "KEEPALIVE_SECONDS", 10.0)

    async def scenario():
        api, seen = _app()
        host = await _module(broker, tmp_path, api)
        nexus = _nexus(broker, 60)
        try:
            response = await call_app(
                nexus, "acme", "i-1", _request("/api/quiet"), service_account="sa1"
            )
            stream = pull_body(await nexus.connect(), response.body_inbox)
            assert await stream.__anext__() == b"data: hello\n\n"
            waiting = asyncio.create_task(stream.__anext__())
            await asyncio.sleep(0.3)
            waiting.cancel()  # the browser left, mid-pull
            await asyncio.gather(waiting, return_exceptions=True)
            started = time.monotonic()
            while not seen.cancelled and time.monotonic() - started < 3:
                await asyncio.sleep(0.05)
            assert seen.cancelled
            assert time.monotonic() - started < 2
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


# -- review round 1 of #108 -------------------------------------------------------


def test_headers_count_toward_what_travels_inline(small_broker, tmp_path):
    """A 40 KiB body fits a 64 KiB message alone, not with 30 KiB of headers:
    it streams instead of failing to send (APP_ERROR)."""

    async def scenario():
        api, _ = _app()
        host = await _module(small_broker, tmp_path, api)
        nexus = _nexus(small_broker, 10)
        try:
            response = await call_app(
                nexus, "acme", "i-1", _request("/api/headers"), service_account="sa1"
            )
            assert response.status == 200 and response.body_follows, response.error
            assert {h.name: h.value for h in response.headers}[
                "x-padding"
            ] == "p" * 30000
            assert await _body(nexus, response) == b"h" * 40960
        finally:
            await host.close()
            await nexus.close()
            await host.session.client.transport.close()

    asyncio.run(scenario())


def test_one_pull_waits_at_a_time(broker, monkeypatch):
    """A pull sent while another waits for the next chunk is refused at once,
    not queued behind it (no backlog of waiting pulls)."""
    monkeypatch.setattr(app_streams, "KEEPALIVE_SECONDS", 1.0)

    async def scenario():
        nexus = _nexus(broker, 60)
        try:
            nc = await nexus.connect()
            source = BodySource(nc)
            await source.start()
            pull = pb.BodyPull(sequence=0).SerializeToString()
            waiting = asyncio.create_task(nc.request(source.inbox, pull, timeout=5))
            await asyncio.sleep(0.1)
            started = time.monotonic()
            second = pb.BodyChunk.FromString(
                (await nc.request(source.inbox, pull, timeout=5)).data
            )
            assert second.error.code == "INVALID_ARGUMENT"
            assert time.monotonic() - started < 0.5
            first = pb.BodyChunk.FromString((await waiting).data)
            assert (first.sequence, first.data, first.error.code) == (0, b"", "")
            await source.close()
        finally:
            await nexus.close()

    asyncio.run(scenario())


def test_an_abort_after_the_whole_body_keeps_its_end(broker):
    """Stopping the module while the reader has yet to take the end of a whole
    body: the reader gets the clean end, not an error."""

    async def scenario():
        nexus = _nexus(broker, 60)
        try:
            nc = await nexus.connect()
            source = BodySource(nc)
            await source.start()
            await source.finish()
            source.abort("MODULE_UNAVAILABLE", "The module stopped")
            assert [chunk async for chunk in pull_body(nc, source.inbox)] == []
            await source.close()
        finally:
            await nexus.close()

    asyncio.run(scenario())
