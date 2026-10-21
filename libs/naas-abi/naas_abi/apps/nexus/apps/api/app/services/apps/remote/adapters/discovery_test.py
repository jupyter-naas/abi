from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters.discovery import (
    DiscoveryRemoteAppDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    AppRequest,
    RemoteApp,
    RemoteAppUnavailable,
)

pytest.importorskip("naas_abi_sdk")
from naas_abi_proto.app.v1 import app_pb2 as pb  # noqa: E402
from naas_abi_sdk.apps import AppDescriptor  # noqa: E402
from naas_abi_sdk.discovery import ModuleInstance  # noqa: E402
from naas_abi_sdk.transport import RPCError  # noqa: E402
from nats.errors import NoRespondersError  # noqa: E402


def _instance(module_id, instance_id, *apps, status="READY"):
    return ModuleInstance(module_id, instance_id, "1.0", 1, status, 0.0, (), apps=tuple(apps))


CONSOLE = AppDescriptor("console", "Console", "Ops", "operations", "🛰", "index.html")


class FakeDiscovery:
    def __init__(self, instances):
        self.instances, self.reads = list(instances), 0

    async def list_modules(self, *, limit, after_instance_id):
        self.reads += 1
        return tuple(self.instances), ""


def _directory(discovery, calls, answers, now=None):
    async def call_app(transport, project, instance_id, request, *, service_account=""):
        calls.append((instance_id, request))
        answer = answers.pop(0) if answers else pb.HttpResponse(status=200, body=b"ok")
        if isinstance(answer, Exception):
            raise answer
        return answer

    clock = now or [0.0]
    return DiscoveryRemoteAppDirectory(
        lambda: (discovery, object(), object(), "acme"),
        clock=lambda: clock[0],
        call_app=call_app,
    )


def test_lists_the_apps_of_ready_instances_once_per_module():
    discovery = FakeDiscovery(
        [
            _instance("acme.research", "i-1", CONSOLE),
            _instance("acme.research", "i-2", CONSOLE),
            _instance("acme.draft", "i-3", CONSOLE, status="STARTING"),
        ]
    )

    apps = asyncio.run(_directory(discovery, [], []).list_apps())

    assert apps == [
        RemoteApp("acme.research", "console", "Console", "Ops", "operations", "🛰", "index.html")
    ]
    assert apps[0].url == "/app-html/remote/acme.research/console/index.html"
    assert apps[0].app_id == "remote/acme.research:console"


def test_forwards_to_a_ready_instance_with_the_root_path():
    calls: list = []
    directory = _directory(
        FakeDiscovery([_instance("acme.research", "i-1", CONSOLE)]),
        calls,
        [pb.HttpResponse(status=201, headers=[pb.Header(name="x", value="1")], body=b"hi")],
    )
    request = AppRequest("POST", "/api/x", "a=1", (("content-type", "text/plain"),), b"b", "u-1")

    answer = asyncio.run(directory.forward("acme.research", "console", request))

    assert (answer.status, answer.headers, answer.body) == (201, (("x", "1"),), b"hi")
    instance_id, sent = calls[0]
    assert instance_id == "i-1"
    assert (sent.app, sent.method, sent.path, sent.query, sent.body, sent.user_id) == (
        "console",
        "POST",
        "/api/x",
        "a=1",
        b"b",
        "u-1",
    )
    assert sent.root_path == "/app-html/remote/acme.research/console"
    assert [(h.name, h.value) for h in sent.headers] == [("content-type", "text/plain")]


@pytest.mark.parametrize(
    "failure",
    [RPCError("MODULE_UNAVAILABLE", "draining"), NoRespondersError()],
)
def test_a_departing_instance_is_retried_elsewhere(failure):
    calls: list = []
    directory = _directory(
        FakeDiscovery(
            [
                _instance("acme.research", "i-1", CONSOLE),
                _instance("acme.research", "i-2", CONSOLE),
            ]
        ),
        calls,
        [failure, pb.HttpResponse(status=200, body=b"ok")],
    )

    answer = asyncio.run(directory.forward("acme.research", "console", AppRequest("GET", "/")))

    assert answer.body == b"ok"
    assert {calls[0][0], calls[1][0]} == {"i-1", "i-2"}


@pytest.mark.parametrize(
    ("failure", "status"),
    [
        (RPCError("APP_NOT_FOUND", "x"), 404),
        (RPCError("PAYLOAD_TOO_LARGE", "x"), 413),
        (RPCError("APP_ERROR", "x"), 502),
        (RPCError("UNAUTHENTICATED", "x"), 502),
        (TimeoutError(), 504),
    ],
)
def test_failures_become_http_statuses(failure, status):
    directory = _directory(
        FakeDiscovery([_instance("acme.research", "i-1", CONSOLE)]), [], [failure]
    )

    with pytest.raises(RemoteAppUnavailable) as raised:
        asyncio.run(directory.forward("acme.research", "console", AppRequest("GET", "/")))

    assert raised.value.status == status


def test_unknown_apps_are_404_after_a_fresh_read():
    discovery = FakeDiscovery([])
    now = [0.0]
    directory = _directory(discovery, [], [], now)

    async def scenario():
        await directory.list_apps()
        now[0] = 2.0
        with pytest.raises(RemoteAppUnavailable) as raised:
            await directory.forward("acme.research", "console", AppRequest("GET", "/"))
        return raised.value.status

    assert asyncio.run(scenario()) == 404
    assert discovery.reads == 2  # the cached snapshot, then a fresh one


def test_unknown_names_read_discovery_at_most_once_a_second():
    """Made-up module or app names cannot make every request read discovery."""
    discovery = FakeDiscovery([_instance("acme.research", "i-1", CONSOLE)])
    now = [0.0]
    directory = _directory(discovery, [], [], now)

    async def miss(name):
        with pytest.raises(RemoteAppUnavailable):
            await directory.forward(name, "console", AppRequest("GET", "/"))

    async def scenario():
        await directory.list_apps()
        now[0] = 5.0
        await asyncio.gather(*(miss(f"made.up{i}") for i in range(20)))
        now[0] = 5.5
        await asyncio.gather(*(miss(f"other{i}") for i in range(20)))

    asyncio.run(scenario())
    assert discovery.reads == 2  # the first listing, then one read for 40 misses


class SlowDiscovery(FakeDiscovery):
    async def list_modules(self, *, limit, after_instance_id):
        self.reads += 1
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")


def test_a_slow_discovery_fails_the_catalog_within_the_refresh_bound():
    discovery = SlowDiscovery([])
    now = [0.0]
    directory = DiscoveryRemoteAppDirectory(
        lambda: (discovery, object(), object(), "acme"),
        clock=lambda: now[0],
        refresh_seconds=0.05,
    )

    async def scenario():
        loop = asyncio.get_running_loop()
        started = loop.time()
        results = await asyncio.gather(
            *(directory.list_apps() for _ in range(10)), return_exceptions=True
        )
        return loop.time() - started, results

    elapsed, results = asyncio.run(scenario())
    # One bounded read; the callers that waited for it fail with it at once.
    assert elapsed < 1.0
    assert discovery.reads == 1
    assert all(isinstance(r, RemoteAppUnavailable) and r.status == 503 for r in results)


def test_discovery_is_read_again_after_a_failure_once_the_retry_delay_passed():
    discovery = SlowDiscovery([])
    now = [0.0]
    directory = DiscoveryRemoteAppDirectory(
        lambda: (discovery, object(), object(), "acme"),
        clock=lambda: now[0],
        refresh_seconds=0.01,
    )

    async def scenario():
        for at in (0.0, 1.0, 4.9, 5.1):
            now[0] = at
            with pytest.raises(RemoteAppUnavailable):
                await directory.list_apps()

    asyncio.run(scenario())
    assert discovery.reads == 2  # at 0 and at 5.1, not in between


def test_discovery_is_read_at_most_every_10_seconds():
    discovery = FakeDiscovery([_instance("acme.research", "i-1", CONSOLE)])
    now = [0.0]
    directory = _directory(discovery, [], [], now)

    async def scenario():
        await directory.list_apps()
        await directory.forward("acme.research", "console", AppRequest("GET", "/"))
        now[0] = 11.0
        await directory.list_apps()

    asyncio.run(scenario())
    assert discovery.reads == 2


def test_a_discovery_failure_is_a_generic_503_and_its_cause_is_logged(caplog):
    class Broken(FakeDiscovery):
        async def list_modules(self, *, limit, after_instance_id):
            raise RuntimeError("discovery internals: KV revision 42 conflict")

    directory = DiscoveryRemoteAppDirectory(lambda: (Broken([]), object(), object(), "acme"))

    with caplog.at_level("WARNING"), pytest.raises(RemoteAppUnavailable) as raised:
        asyncio.run(directory.list_apps())

    assert (raised.value.status, raised.value.reason) == (503, "Module discovery is unavailable")
    assert "KV revision 42" in caplog.text  # the operator still sees the cause
    assert "KV revision 42" not in raised.value.reason


# -- bodies over a real broker (A6, A15, A18) -------------------------------------

nats_server = pytest.mark.skipif(
    __import__("shutil").which("nats-server") is None, reason="nats-server not installed"
)


@pytest.fixture
def broker():
    import socket
    import subprocess
    import time

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


def _wired(broker, call_app):
    from naas_abi_sdk.transport import Transport

    transport = Transport(broker, "nexus-token")
    directory = DiscoveryRemoteAppDirectory(
        lambda: (
            FakeDiscovery([_instance("acme.research", "i-1", CONSOLE)]),
            transport,
            transport,
            "acme",
        ),
        call_app=call_app,
    )
    return directory, transport


@nats_server
def test_an_upload_the_browser_drops_frees_its_slot_at_once(broker):
    """A18: the module's app hears of it now, not after its 60 s idle limit."""
    from naas_abi_sdk.app_streams import pull_body
    from starlette.requests import ClientDisconnect

    seen: dict = {}
    apps: list[asyncio.Task] = []

    async def module(transport, project, instance_id, request, *, service_account=""):
        nc = await transport.connect()

        async def app():  # runs in the module's process, apart from this call
            try:
                async for _ in pull_body(nc, request.body_inbox):
                    pass
            except RPCError as exc:
                seen["error"] = exc.code

        apps.append(asyncio.create_task(app()))
        await asyncio.sleep(3600)  # it never answers once cut off

    async def browser():
        yield b"x" * (300 * 1024)
        raise ClientDisconnect()

    async def scenario():
        directory, transport = _wired(broker, module)
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            with pytest.raises(RemoteAppUnavailable) as cut:
                await directory.forward(
                    "acme.research",
                    "console",
                    AppRequest("PUT", "/api/upload", body_stream=browser(), max_body_bytes=10**9),
                )
            assert cut.value.status == 400
            await asyncio.wait_for(apps[0], 1)
            assert loop.time() - started < 3
            assert seen == {"error": "CANCELLED"}
        finally:
            await transport.close()

    asyncio.run(scenario())


@nats_server
def test_a_response_that_breaks_off_raises_and_closing_tells_the_module(broker):
    """A6: the body's iterator raises, so the server aborts the connection.
    Closing a body before its first chunk tells the module too."""
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import RemoteAppStreamFailed
    from naas_abi_sdk.app_streams import BodySource

    async def scenario():
        held: list = []

        async def module(transport, project, instance_id, request, *, service_account=""):
            source = BodySource(await transport.connect())
            await source.start()
            held.append(source)
            return pb.HttpResponse(status=200, body_follows=True, body_inbox=source.inbox)

        directory, transport = _wired(broker, module)
        try:
            answer = await directory.forward("acme.research", "console", AppRequest("GET", "/x"))
            body = answer.body_stream.__aiter__()
            await held[0].put(b"part")
            assert await body.__anext__() == b"part"
            held[0].abort("APP_ERROR", "App failed")
            with pytest.raises(RemoteAppStreamFailed):
                await body.__anext__()

            unread = await directory.forward("acme.research", "console", AppRequest("GET", "/y"))
            await unread.body_stream.aclose()  # the browser left before any chunk
            await asyncio.wait_for(held[1].gone.wait(), 2)
            for source in held:
                await source.close()
        finally:
            await transport.close()

    asyncio.run(scenario())


def test_the_workspace_reaches_the_module():
    """A15: the module learns the workspace the user opened the app from."""
    calls: list = []
    directory = _directory(FakeDiscovery([_instance("acme.research", "i-1", CONSOLE)]), calls, [])

    asyncio.run(
        directory.forward(
            "acme.research",
            "console",
            AppRequest("GET", "/", user_id="u-1", workspace_id="ws-1"),
        )
    )

    assert (calls[0][1].user_id, calls[0][1].workspace_id) == ("u-1", "ws-1")


@pytest.mark.parametrize("code", ["APP_ERROR", "DEADLINE_EXCEEDED"])
def test_a_response_that_fails_mid_stream_is_not_ended_cleanly(monkeypatch, code):
    """The status line is out: only an error makes the server abort the
    connection, so the browser does not save a truncated file as complete."""
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters import discovery
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import RemoteAppStreamFailed
    from naas_abi_sdk import app_streams

    async def pull_body(nc, inbox):
        yield b"first"
        raise RPCError(code, "gone")

    monkeypatch.setattr(app_streams, "pull_body", pull_body)

    async def read():
        received = []
        async for chunk in discovery._Pulled(object(), "_INBOX.x"):
            received.append(chunk)
        return received

    with pytest.raises(RemoteAppStreamFailed):
        asyncio.run(read())


def test_a_browser_that_drops_its_upload_fails_the_body():
    """Else the app waits in receive() until its idle limit."""
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters import discovery
    from starlette.requests import ClientDisconnect

    class Source:
        def __init__(self):
            self.chunks, self.failed, self.finished = [], None, False

        async def put(self, chunk):
            self.chunks.append(chunk)

        async def finish(self):
            self.finished = True

        def abort(self, code, message):
            self.failed = code

    async def browser():
        yield b"part"
        raise ClientDisconnect()

    source = Source()
    nc = type("NC", (), {"max_payload": 1024 * 1024})()
    with pytest.raises(discovery.UploadCut):
        asyncio.run(discovery._pump(browser(), source, 0, nc))

    assert (source.failed, source.finished) == ("CANCELLED", False)


def test_an_unknown_app_is_not_looked_up_again_for_5_seconds():
    """Stale tabs polling a removed module's assets must not hold the discovery
    lock that every remote app request waits on."""
    discovery = FakeDiscovery([])
    now = [0.0]
    directory = _directory(discovery, [], [], now)

    async def missing():
        with pytest.raises(RemoteAppUnavailable):
            await directory.forward("acme.gone", "console", AppRequest("GET", "/"))

    async def scenario():
        await directory.list_apps()
        now[0] = 2.0
        await missing()  # a fresh read
        assert discovery.reads == 2
        now[0] = 6.0
        await missing()  # neither: the snapshot is current, the miss is recent
        assert discovery.reads == 2
        now[0] = 8.0
        await missing()  # the miss is stale: one fresh read
        assert discovery.reads == 3
        discovery.instances.append(_instance("acme.gone", "i-9", CONSOLE))
        now[0] = 20.0
        answer = await directory.forward("acme.gone", "console", AppRequest("GET", "/"))
        assert answer.body == b"ok"

    asyncio.run(scenario())
