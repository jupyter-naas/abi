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
