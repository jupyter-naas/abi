import asyncio
import json
import sys
import types
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


def _session():
    call = AsyncMock(
        return_value=discovery_pb.AuthorizeAppResponse(
            caller_identity="u-7",
            caller_user_id="u-7",
            caller_principal_id="sa_api",
            caller_principal_kind="service_account",
            caller_principal_name="api",
        )
    )
    return SimpleNamespace(
        instance_id="i-1",
        service_account="sa1",
        lease_token="l" * 32,
        client=SimpleNamespace(_call=call, project="acme"),
    )


def _host(tmp_path, asgi=None):
    descriptor = read_app(_site(tmp_path))
    return AppHost(_session(), {"console": (descriptor, asgi)})


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
    assert (
        app_subject("acme", "sa1", "i-1", "console")
        == "abi.mod.acme.sa1.i-1.app.console.http"
    )


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
            "principal": request.scope["abi"]["principal"],
            "q": request.query_params.get("q"),
            "url": str(request.url_for("whoami")),
        }

    @app.post("/api/echo")
    async def echo(payload: dict):
        return payload

    async def scenario():
        host = _host(tmp_path, app)
        # The request's user_id is data: the app sees the user discovery verified.
        response = await _send(
            host,
            _request(
                "/api/whoami",
                query="q=1",
                user_id="forged",
                principal_id="forged",
                principal_kind="user",
                principal_name="api",
            ),
        )
        assert response.status == 200, response.body
        body = json.loads(response.body)
        assert body["user"] == "u-7" and body["q"] == "1"
        # So is the actor: the account that holds the credential.
        assert body["principal"] == {
            "id": "sa_api",
            "kind": "service_account",
            "name": "api",
        }
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
        assert nc.subscribe.await_args.args[0] == "abi.mod.acme.sa1.i-1.app.console.http"
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
