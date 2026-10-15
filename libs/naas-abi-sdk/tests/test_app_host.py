import asyncio
import json
import sys
import types
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.app.v1 import app_pb2 as pb
from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb

from naas_abi_sdk.app_host import AppHost, app_subject
from naas_abi_sdk.app_streams import INLINE_BYTES
from naas_abi_sdk.apps import AppDescriptor, discover_apps, read_app
from naas_abi_sdk.discovery import module_descriptor
from naas_abi_sdk.module import BaseModule
from naas_abi_sdk.transport import RPCError


def _site(tmp_path, name="console", manifest=None):
    folder = tmp_path / "apps" / name
    (folder / "assets").mkdir(parents=True)
    (folder / "manifest.json").write_text(
        json.dumps(
            manifest
            or {
                "name": "Console",
                "description": "Ops console",
                "category": "operations",
                "url": "html:index.html",
                "icon_emoji": "🛰",
            }
        )
    )
    (folder / "index.html").write_text("<h1>console</h1>")
    (folder / "assets" / "app.js").write_text("console.log(1)")
    (folder / "server.py").write_text("SECRET = 1")
    return folder


class FakeMsg:
    def __init__(self, request: pb.HttpRequest, token="caller-token", data=None):
        self.data = request.SerializeToString() if data is None else data
        self.headers = {"Nats-Auth-Token": token}
        self.reply = "_INBOX.x"
        self.sent: list[bytes] = []
        self._client = SimpleNamespace(
            max_payload=8 * 1024 * 1024, publish=self._publish
        )

    async def _publish(self, subject, data, headers=None):
        self.sent.append(data)

    @property
    def response(self) -> pb.HttpResponse:
        return pb.HttpResponse.FromString(self.sent[-1])


def _session(caller="api"):
    call = AsyncMock(
        return_value=discovery_pb.AuthorizeAppResponse(caller_identity=caller)
    )
    # The host reads the broker's limit to decide what travels inline.
    nc = SimpleNamespace(max_payload=8 * 1024 * 1024)
    return SimpleNamespace(
        instance_id="i-1",
        lease_token="l" * 32,
        client=SimpleNamespace(
            _call=call,
            project="acme",
            transport=SimpleNamespace(connect=AsyncMock(return_value=nc)),
        ),
    )


def _host(tmp_path, asgi=None, caller="api"):
    descriptor = read_app(_site(tmp_path))
    return AppHost(_session(caller), {"console": (descriptor, asgi)})


def _request(path="/", method="GET", **fields):
    return pb.HttpRequest(
        app="console",
        method=method,
        path=path,
        root_path="/app-html/remote/acme.research/console",
        **fields,
    )


async def _send(host, request, **kwargs):
    msg = FakeMsg(request, **kwargs)
    await host._handle("console", msg)
    return msg.response


def _headers(response) -> dict[str, str]:
    return {h.name: h.value for h in response.headers}


def test_the_subject_is_instance_addressed():
    assert app_subject("acme", "i-1", "console") == "abi.mod.acme.i-1.app.console.http"


# -- static files -------------------------------------------------------------------


def test_static_files_and_the_entry_page(tmp_path):
    async def scenario():
        host = _host(tmp_path)
        root = await _send(host, _request("/"))
        assert (root.status, root.body) == (200, b"<h1>console</h1>")
        assert _headers(root)["content-type"] == "text/html"
        script = await _send(host, _request("/assets/app.js"))
        assert script.status == 200 and script.body == b"console.log(1)"
        assert "javascript" in _headers(script)["content-type"]
        head = await _send(host, _request("/index.html", method="HEAD"))
        assert head.status == 200 and head.body == b""

    asyncio.run(scenario())


def test_an_etag_revalidates_without_the_body(tmp_path):
    async def scenario():
        host = _host(tmp_path)
        first = await _send(host, _request("/index.html"))
        etag = _headers(first)["etag"]
        again = _request("/index.html")
        again.headers.add(name="If-None-Match", value=etag)
        cached = await _send(host, again)
        assert (cached.status, cached.body) == (304, b"")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "path",
    [
        "/../secret",
        "/assets/../../x.html",
        "/server.py",
        "/manifest.json",
        "/missing.js",
        "//etc/passwd",
    ],
)
def test_only_browser_assets_of_the_folder_are_served(tmp_path, path):
    (tmp_path / "secret").write_text("nope")
    (tmp_path / "x.html").write_text("nope")

    async def scenario():
        response = await _send(_host(tmp_path), _request(path))
        assert response.status == 404
        assert b"nope" not in response.body and b"SECRET" not in response.body

    asyncio.run(scenario())


# -- the ASGI backend ---------------------------------------------------------------


def test_a_fastapi_backend_answers_other_paths(tmp_path):
    fastapi = pytest.importorskip("fastapi")
    app = fastapi.FastAPI()

    @app.get("/api/whoami")
    async def whoami(request: fastapi.Request):
        return {
            "user": request.scope["abi"]["user_id"],
            "q": request.query_params.get("q"),
            "url": str(request.url_for("whoami")),
        }

    @app.post("/api/echo")
    async def echo(payload: dict):
        return payload

    async def scenario():
        host = _host(tmp_path, app)
        response = await _send(
            host, _request("/api/whoami", query="q=1", user_id="u-7")
        )
        assert response.status == 200, response.body
        body = json.loads(response.body)
        assert body["user"] == "u-7" and body["q"] == "1"
        # URLs the app generates point back through Nexus.
        assert body["url"].endswith("/app-html/remote/acme.research/console/api/whoami")
        posted = _request("/api/echo", method="POST", body=b'{"a": 1}')
        posted.headers.add(name="Content-Type", value="application/json")
        echoed = await _send(host, posted)
        assert (echoed.status, json.loads(echoed.body)) == (200, {"a": 1})
        # Files still come from the folder first.
        assert (await _send(host, _request("/"))).body == b"<h1>console</h1>"
        missing = await _send(host, _request("/api/nothing"))
        assert missing.status == 404

    asyncio.run(scenario())


def test_only_nexus_calls_an_app_on_behalf_of_a_user(tmp_path):
    """A module may call another module's app, but never as a user (A8)."""
    fastapi = pytest.importorskip("fastapi")
    app = fastapi.FastAPI()

    @app.get("/api/whoami")
    async def whoami(request: fastapi.Request):
        return request.scope["abi"]

    async def scenario():
        nexus = _host(tmp_path / "nexus", app)
        answered = await _send(
            nexus, _request("/api/whoami", user_id="u-7", workspace_id="ws-1")
        )
        assert json.loads(answered.body) == {
            "user_id": "u-7",
            "workspace_id": "ws-1",
            "caller": "api",
        }
        module = _host(tmp_path / "module", app, caller="acme.billing")
        forged = await _send(module, _request("/api/whoami", user_id="u-7"))
        assert forged.error.code == "PERMISSION_DENIED"
        # A15: nor in a workspace.
        placed = await _send(module, _request("/api/whoami", workspace_id="ws-1"))
        assert placed.error.code == "PERMISSION_DENIED"
        assert "acme.billing" in forged.error.message
        anonymous = await _send(module, _request("/api/whoami"))
        assert json.loads(anonymous.body) == {
            "user_id": "",
            "workspace_id": "",
            "caller": "acme.billing",
        }

    asyncio.run(scenario())


def test_without_a_backend_unknown_paths_are_404(tmp_path):
    async def scenario():
        response = await _send(_host(tmp_path), _request("/api/x", method="POST"))
        assert response.status == 404

    asyncio.run(scenario())


def test_a_whole_small_response_travels_inline(tmp_path):
    """Larger, or sent in parts, it streams (test_app_streams.py)."""

    async def small(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"x" * INLINE_BYTES})

    async def scenario():
        response = await _send(_host(tmp_path, small), _request("/small"))
        assert response.status == 200 and not response.body_follows
        assert len(response.body) == INLINE_BYTES

    asyncio.run(scenario())


def test_a_failing_backend_is_an_app_error(tmp_path):
    async def broken(scope, receive, send):
        raise RuntimeError("boom")

    async def scenario():
        response = await _send(_host(tmp_path, broken), _request("/x"))
        assert response.error.code == "APP_ERROR"
        assert "boom" not in response.error.message

    asyncio.run(scenario())


@pytest.mark.parametrize("code", ["MODULE_UNAVAILABLE", "UNAVAILABLE", "LEASE_EXPIRED"])
def test_an_rpc_error_raised_by_the_app_is_an_app_error(tmp_path, code):
    """Nexus resends retryable codes elsewhere, assuming the app never ran: an
    app whose own downstream call failed must not have its POST run twice."""

    async def calls_downstream(scope, receive, send):
        raise RPCError(code, "downstream module gone")

    async def scenario():
        response = await _send(
            _host(tmp_path, calls_downstream), _request("/x", method="POST")
        )
        assert response.error.code == "APP_ERROR"

    asyncio.run(scenario())


def test_lifespan_runs_startup_and_shutdown(tmp_path):
    events = []

    async def app(scope, receive, send):
        assert scope["type"] == "lifespan"
        while True:
            message = await receive()
            events.append(message["type"])
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            else:
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def scenario():
        host = _host(tmp_path, app)
        nc = SimpleNamespace(subscribe=AsyncMock(), flush=AsyncMock())
        host.session.client.transport = SimpleNamespace(
            connect=AsyncMock(return_value=nc)
        )
        await host.start()
        assert nc.subscribe.await_args.args[0] == "abi.mod.acme.i-1.app.console.http"
        await host.close()

    asyncio.run(scenario())
    assert events == ["lifespan.startup", "lifespan.shutdown"]


def test_an_app_without_lifespan_support_still_starts(tmp_path):
    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            raise RuntimeError("no lifespan")

    async def scenario():
        host = _host(tmp_path, app)
        nc = SimpleNamespace(subscribe=AsyncMock(), flush=AsyncMock())
        host.session.client.transport = SimpleNamespace(
            connect=AsyncMock(return_value=nc)
        )
        await host.start()
        await host.close()

    asyncio.run(scenario())


# -- authorization and limits ----------------------------------------------------


def test_every_caller_is_authorized_through_discovery(tmp_path):
    async def scenario():
        host = _host(tmp_path)
        await _send(host, _request("/"))
        request = host.session.client._call.await_args.args[1]
        assert host.session.client._call.await_args.args[0] == "authorize_app"
        assert (request.app_name, request.caller_token) == ("console", "caller-token")
        assert (request.instance_id, request.lease_token) == ("i-1", "l" * 32)
        host.session.client._call.side_effect = RPCError("UNAUTHENTICATED", "bad token")
        refused = await _send(host, _request("/"), token="forged")
        assert refused.error.code == "UNAUTHENTICATED" and refused.body == b""

    asyncio.run(scenario())


def test_draining_and_oversized_requests_are_refused(tmp_path):
    async def scenario():
        host = _host(tmp_path)
        big = await _send(host, _request("/"), data=b"x" * (2 * 1024 * 1024))
        assert big.error.code == "PAYLOAD_TOO_LARGE"
        other = await _send(host, pb.HttpRequest(app="other", method="GET", path="/"))
        assert other.error.code == "INVALID_ARGUMENT"
        host.closing = True
        draining = await _send(host, _request("/"))
        assert draining.error.code == "MODULE_UNAVAILABLE"

    asyncio.run(scenario())


def _in_flight(host, request):
    """Deliver ``request`` as the subscription does: in its own task."""
    msg = FakeMsg(request)
    host.subscriptions.append(
        SimpleNamespace(drain=AsyncMock(), unsubscribe=AsyncMock())
    )
    return msg, host.calls.callback(partial(host._handle, "console"))(msg)


def test_draining_lets_requests_in_progress_answer(tmp_path):
    """On SIGTERM a request already running answers; Nexus does not wait 65 s
    for a reply that never comes."""
    release = asyncio.Event()

    async def slow(scope, receive, send):
        await release.wait()
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"done"})

    async def scenario():
        host = _host(tmp_path, slow)
        msg, receive = _in_flight(host, _request("/x", method="POST"))
        await receive
        subscription = host.subscriptions[0]
        drain = asyncio.create_task(host.drain(30))
        await asyncio.sleep(0.05)
        assert not drain.done()
        subscription.drain.assert_awaited()  # new requests go elsewhere
        release.set()
        await asyncio.wait_for(drain, 5)
        assert (msg.response.status, msg.response.body) == (201, b"done")
        await host.close()

    asyncio.run(scenario())


def test_draining_gives_up_after_its_timeout(tmp_path):
    async def stuck(scope, receive, send):
        await asyncio.Event().wait()

    async def scenario():
        host = _host(tmp_path, stuck)
        _, receive = _in_flight(host, _request("/x"))
        await receive
        await asyncio.wait_for(host.drain(0.05), 5)
        await host.close()  # cancels what is still running

    asyncio.run(scenario())


class _QueuedSubscription:
    """nats-py's drain: unsubscribe, then wait until the queued messages are
    handed to the callback, one at a time."""

    def __init__(self, cb, queued):
        self.cb, self.queued = cb, list(queued)
        self.unsubscribe = AsyncMock()

    async def drain(self):
        for msg in self.queued:
            await self.cb(msg)


def test_draining_keeps_to_its_deadline_with_calls_in_flight(tmp_path):
    """Every slot busy, a request queued behind them: the queued one is refused
    for another instance at once, and the drain ends at its timeout."""

    running = asyncio.Event()

    async def stuck(scope, receive, send):
        running.set()
        await asyncio.Event().wait()

    async def scenario():
        host = AppHost(
            _session(),
            {"console": (read_app(_site(tmp_path)), stuck)},
            max_concurrency=1,
        )
        receive = host._receiver("console")
        await receive(FakeMsg(_request("/x", method="POST")))  # takes the only slot
        await asyncio.wait_for(running.wait(), 5)
        queued = FakeMsg(_request("/y", method="POST"))
        host.subscriptions.append(_QueuedSubscription(receive, [queued]))
        loop = asyncio.get_running_loop()
        started = loop.time()
        await asyncio.wait_for(host.drain(0.3), 5)
        assert loop.time() - started < 1.0
        assert host.calls.in_flight == 1  # still running: close() cancels it
        assert queued.response.error.code == "MODULE_UNAVAILABLE"
        await host.close()

    asyncio.run(scenario())


def test_a_subscription_drain_that_hangs_does_not_outlast_the_timeout(tmp_path):
    async def scenario():
        host = _host(tmp_path)
        host.subscriptions.append(
            SimpleNamespace(drain=asyncio.Event().wait, unsubscribe=AsyncMock())
        )
        await asyncio.wait_for(host.drain(0.1), 2)
        await host.close()

    asyncio.run(scenario())


def test_draining_with_nats_closed_still_waits_for_calls(tmp_path):
    """nats-py refuses to drain on a closed or draining connection: the host
    unsubscribes if it can and still lets the call in progress answer."""
    from nats.errors import ConnectionClosedError

    release = asyncio.Event()

    async def slow(scope, receive, send):
        await release.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def scenario():
        host = _host(tmp_path, slow)
        msg, receive = _in_flight(host, _request("/x"))
        await receive
        subscription = host.subscriptions[0]
        subscription.drain.side_effect = ConnectionClosedError
        subscription.unsubscribe.side_effect = ConnectionClosedError
        drain = asyncio.create_task(host.drain(30))
        await asyncio.sleep(0.05)
        assert not drain.done()
        subscription.unsubscribe.assert_awaited()
        release.set()
        await asyncio.wait_for(drain, 5)
        assert msg.response.status == 200
        await host.close()

    asyncio.run(scenario())


def test_one_host_failing_to_drain_does_not_stop_the_others():
    from naas_abi_sdk.module import _drain_hosts

    async def scenario():
        app_host = SimpleNamespace(drain=AsyncMock(side_effect=RuntimeError("nats")))
        agent_host = SimpleNamespace(drain=AsyncMock())
        job_host = SimpleNamespace(drain=AsyncMock())
        await _drain_hosts(agent_host, job_host, None, 1.0, app_host)
        agent_host.drain.assert_awaited_once_with(1.0)
        job_host.drain.assert_awaited_once_with(1.0)

    asyncio.run(scenario())


# -- declaring apps -------------------------------------------------------------------


def test_apps_are_found_next_to_the_module_package(tmp_path):
    _site(tmp_path)
    _site(tmp_path, "reports", {"name": "Reports"})
    (tmp_path / "apps" / "notes").mkdir()  # no manifest: not an app
    package = types.ModuleType("fake_remote_module")
    package.__file__ = str(tmp_path / "__init__.py")
    sys.modules["fake_remote_module"] = package
    try:

        class ABIModule(BaseModule):
            module_id = "acme.research"

        ABIModule.__module__ = "fake_remote_module"
        apps = discover_apps(ABIModule)
        assert [a.name for a in apps] == ["console", "reports"]
        assert apps[0] == AppDescriptor(
            name="console",
            title="Console",
            description="Ops console",
            category="operations",
            icon_emoji="🛰",
            entry="index.html",
            root=tmp_path / "apps" / "console",
        )
        assert (apps[1].title, apps[1].category) == ("Reports", "module")
        descriptor = module_descriptor(ABIModule, "acme.research", ())
        assert [a.name for a in descriptor.apps] == ["console", "reports"]
        assert descriptor.apps[0].entry == "index.html"
    finally:
        del sys.modules["fake_remote_module"]


def test_declared_apps_win_over_the_folder(tmp_path):
    class ABIModule(BaseModule):
        apps = (AppDescriptor("api-only", title="API"),)

    assert [a.name for a in ABIModule.get_apps()] == ["api-only"]


@pytest.mark.parametrize("name", ["a.b", "a/b", "", "x" * 65])
def test_app_names_are_url_segments(name):
    with pytest.raises(ValueError, match="URL segment"):
        AppDescriptor(name)


def test_expose_app_needs_a_declared_app():
    class ABIModule(BaseModule):
        apps = (AppDescriptor("console"),)

    module = ABIModule(SimpleNamespace(), ABIModule.Configuration())

    async def app(scope, receive, send): ...

    module.expose_app("console", app)
    with pytest.raises(ValueError, match="already registered"):
        module.expose_app("console", app)
    with pytest.raises(ValueError, match="Declare the app"):
        module.expose_app("other", app)


# -- review findings of 2026-10-13 (A9, A10, A23-A25, A28) ----------------------------


def test_an_answer_too_large_for_a_message_is_an_error_not_silence(tmp_path):
    """A9: Nexus gets an error at once instead of waiting for its timeout."""

    async def huge_headers(scope, receive, send):
        headers = [(b"x-padding", b"p" * (96 * 1024))]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": b"ok"})

    async def scenario():
        msg = FakeMsg(_request("/x"))
        msg._client.max_payload = 64 * 1024
        await _host(tmp_path, huge_headers)._handle("console", msg)
        assert msg.response.error.code == "APP_ERROR"
        assert "too large" in msg.response.error.message

    asyncio.run(scenario())


def test_a_failed_send_of_the_answer_is_followed_by_an_error(tmp_path):
    """A9: the first send fails; the module still answers."""

    async def scenario():
        msg = FakeMsg(_request("/"))
        sent = msg._publish
        calls = []

        async def flaky(subject, data, headers=None):
            calls.append(data)
            if len(calls) == 1:
                raise ConnectionError("broker hiccup")
            await sent(subject, data, headers)

        msg._client.publish = flaky
        await _host(tmp_path)._handle("console", msg)
        assert len(calls) == 2
        assert msg.response.error.code == "APP_ERROR"

    asyncio.run(scenario())


def test_an_rpc_error_of_the_app_itself_is_an_app_error(tmp_path):
    """A10: an app whose own call failed is not "the module is unavailable",
    which Nexus would resend to another instance after the app ran."""

    async def calls_a_service(scope, receive, send):
        raise RPCError("UNAVAILABLE", "the vector store is down")

    async def scenario():
        response = await _send(_host(tmp_path, calls_a_service), _request("/x"))
        assert response.error.code == "APP_ERROR"
        assert "vector store" not in response.error.message

    asyncio.run(scenario())


def test_a_header_that_is_not_latin_1_is_refused(tmp_path):
    """A23: refused as a bad request, not an app failure."""

    async def app(scope, receive, send):  # pragma: no cover - never reached
        raise AssertionError("the app must not run")

    async def scenario():
        request = _request("/x")
        request.headers.add(name="X-Label", value="café ☕")
        response = await _send(_host(tmp_path, app), request)
        assert response.error.code == "INVALID_ARGUMENT"

    asyncio.run(scenario())


def test_head_and_get_of_a_file_carry_its_length(tmp_path):
    """A23: HEAD answers the length GET would send."""

    async def scenario():
        host = _host(tmp_path)
        head = await _send(host, _request("/index.html", method="HEAD"))
        get = await _send(host, _request("/index.html"))
        size = str(len(b"<h1>console</h1>"))
        assert (
            _headers(head)["content-length"] == size == _headers(get)["content-length"]
        )
        assert head.body == b""

    asyncio.run(scenario())


def test_the_apps_content_length_reaches_nexus(tmp_path):
    """A6: Nexus forwards it, so a cut stream is seen as cut."""

    async def app(scope, receive, send):
        headers = [(b"content-length", b"2"), (b"connection", b"close")]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": b"ok"})

    async def scenario():
        response = await _send(_host(tmp_path, app), _request("/x"))
        assert _headers(response) == {"content-length": "2"}

    asyncio.run(scenario())


def test_a_nul_in_a_path_is_not_found(tmp_path):
    """A24: not an error the module logs as an app failure."""

    async def scenario():
        response = await _send(_host(tmp_path), _request("/index.html\x00.js"))
        assert response.status == 404

    asyncio.run(scenario())


def test_the_lifespan_state_reaches_each_request(tmp_path):
    """A25: a FastAPI lifespan that yields its state starts, and requests see it."""
    fastapi = pytest.importorskip("fastapi")
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        yield {"greeting": "hello"}

    app = fastapi.FastAPI(lifespan=lifespan)

    @app.get("/api/greeting")
    async def greeting(request: fastapi.Request):
        return {"greeting": request.state.greeting}

    async def scenario():
        host = _host(tmp_path, app)
        nc = SimpleNamespace(
            subscribe=AsyncMock(), flush=AsyncMock(), max_payload=8 * 1024 * 1024
        )
        host.session.client.transport = SimpleNamespace(
            connect=AsyncMock(return_value=nc)
        )
        await host.start()
        try:
            response = await _send(host, _request("/api/greeting"))
            assert (response.status, json.loads(response.body)) == (
                200,
                {"greeting": "hello"},
            )
        finally:
            await host.close()

    asyncio.run(scenario())


def test_requests_with_one_token_share_one_authorization(tmp_path):
    """A28: a page loading its files at once asks discovery once."""

    async def scenario():
        host = _host(tmp_path)
        call = host.session.client._call
        answer = call.return_value

        async def slow(*args, **kwargs):
            await asyncio.sleep(0.05)
            return answer

        call.side_effect = slow
        responses = await asyncio.gather(
            *(_send(host, _request("/assets/app.js")) for _ in range(20))
        )
        assert all(r.status == 200 for r in responses)
        assert call.await_count == 1
        call.side_effect = RPCError("UNAUTHENTICATED", "bad token")
        refused = await asyncio.gather(
            *(_send(host, _request("/"), token="other") for _ in range(5))
        )
        assert {r.error.code for r in refused} == {"UNAUTHENTICATED"}
        assert call.await_count == 2

    asyncio.run(scenario())


def test_a_finished_body_outlasts_the_readers_retry_of_its_last_pull():
    """A21: a lost reply to the last pull is asked for again after the reader's
    pull timeout; the holder must still be there to answer it."""
    from naas_abi_sdk import app_streams

    assert app_streams.LINGER_SECONDS > app_streams.PULL_TIMEOUT_SECONDS


def test_closing_lets_the_reader_take_the_error_and_keeps_the_cancel(tmp_path):
    """Review round 1: close() cancels a stream task already waiting for its
    reader. The reader still gets CLOSE_SECONDS to take the error close() put
    in (else its pull waits for its timeout), and the task ends cancelled."""

    class Source:
        def __init__(self):
            self.done, self.closed = asyncio.Event(), False

        async def settled(self):
            await self.done.wait()

        async def close(self):
            self.closed = True

    async def scenario():
        host, source = _host(tmp_path), Source()
        task = asyncio.create_task(host._settle(source))
        await asyncio.sleep(0.05)
        host.closing = True  # as close() does, before cancelling
        task.cancel()
        await asyncio.sleep(0.1)
        assert not source.closed  # the reader is taking the error
        source.done.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert source.closed

    asyncio.run(scenario())
