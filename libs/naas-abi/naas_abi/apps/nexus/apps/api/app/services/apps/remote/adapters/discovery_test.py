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
    async def call_app(transport, project, instance_id, request):
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
    directory = _directory(discovery, [], [])

    async def scenario():
        await directory.list_apps()
        with pytest.raises(RemoteAppUnavailable) as raised:
            await directory.forward("acme.research", "console", AppRequest("GET", "/"))
        return raised.value.status

    assert asyncio.run(scenario()) == 404
    assert discovery.reads == 2  # the cached snapshot, then a fresh one


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


@pytest.mark.parametrize("code", ["APP_ERROR", "DEADLINE_EXCEEDED"])
def test_a_response_that_fails_mid_stream_is_not_ended_cleanly(monkeypatch, code):
    """The status line is out: only an error makes the server abort the
    connection, so the browser does not save a truncated file as complete."""
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters import discovery
    from naas_abi_sdk import app_streams

    async def pull_body(nc, inbox):
        yield b"first"
        raise RPCError(code, "gone")

    monkeypatch.setattr(app_streams, "pull_body", pull_body)

    async def read():
        received = []
        async for chunk in discovery._pulled(object(), "_INBOX.x"):
            received.append(chunk)
        return received

    with pytest.raises(RPCError):
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

        async def fail(self, code, message):
            self.failed = code

    async def browser():
        yield b"part"
        raise ClientDisconnect()

    source = Source()
    nc = type("NC", (), {"max_payload": 1024 * 1024})()
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
        await missing()  # snapshot, then a fresh read
        now[0] = 4.0
        await missing()  # neither: the snapshot is current, the miss is recent
        assert discovery.reads == 2
        now[0] = 6.0
        await missing()  # the miss is stale: one fresh read
        assert discovery.reads == 3
        discovery.instances.append(_instance("acme.gone", "i-9", CONSOLE))
        now[0] = 20.0
        answer = await directory.forward("acme.gone", "console", AppRequest("GET", "/"))
        assert answer.body == b"ok"

    asyncio.run(scenario())
