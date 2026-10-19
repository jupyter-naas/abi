"""The /idp route: one bound module, an allow-list of paths, its own cookies."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters.discovery import (
    DiscoveryRemoteAppDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters.in_memory import (
    InMemoryRemoteAppDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    AppRequest,
    AppResponse,
    RemoteApp,
    RemoteAppUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.idp import binding
from naas_abi.apps.nexus.apps.api.app.services.idp import http_routes as http
from naas_abi.apps.nexus.apps.api.app.services.idp.binding import IdpBinding, IdpTarget
from naas_abi.apps.nexus.apps.api.app.services.idp.paths import is_idp_path

IDP = RemoteApp("idp", "idp")
TARGET = IdpTarget("SA-IDP", "https://abi.example/idp")


def target_binding(**errors) -> IdpBinding:
    def providers():
        if "not_configured" in errors:
            return [SimpleNamespace(provisioning="none", issuer="https://x")]
        return [SimpleNamespace(provisioning="builtin", issuer=TARGET.issuer)]

    def project():
        if "down" in errors:
            raise binding.IdpUnavailable("no discovery")
        return "proj"

    return IdpBinding(providers, project, lambda project: TARGET.service_account)


@pytest.fixture(autouse=True)
def bound():
    previous = binding.configure(target_binding())
    yield
    binding.configure(previous)


@dataclass
class Seen:
    requests: list[AppRequest] = field(default_factory=list)
    accounts: list[str | None] = field(default_factory=list)


class Directory(InMemoryRemoteAppDirectory):
    """Records who each request was bound to."""

    def __init__(self, seen: Seen, handler):
        super().__init__({IDP: handler})
        self.seen = seen

    async def forward(self, module_id, app, request, *, service_account=None):
        self.seen.accounts.append(service_account)
        return await super().forward(module_id, app, request, service_account=service_account)


def serve(monkeypatch, answer=None) -> tuple[TestClient, Seen]:
    seen = Seen()

    async def handler(request: AppRequest) -> AppResponse:
        seen.requests.append(request)
        if answer is not None:
            return answer
        return AppResponse(200, (("content-type", "application/json"),), b"{}")

    directory = Directory(seen, handler)
    monkeypatch.setattr(http, "get_remote_app_directory", lambda: directory)
    app = FastAPI()
    app.add_api_route("/idp/{path:path}", http.serve_idp, methods=http.METHODS)
    return TestClient(app, base_url="https://abi.example"), seen


def answering(monkeypatch, headers=(), status=200, body=b"<html></html>"):
    return serve(monkeypatch, AppResponse(status, tuple(headers), body))[0]


# -- who answers ----------------------------------------------------------------


def test_the_request_goes_to_the_bound_account_only(monkeypatch):
    client, seen = serve(monkeypatch)
    assert client.get("/idp/.well-known/openid-configuration").status_code == 200
    assert seen.accounts == ["SA-IDP"]
    request = seen.requests[0]
    assert (request.path, request.root_path, request.user_id) == (
        "/.well-known/openid-configuration",
        "/idp",
        "",
    )


def test_no_builtin_provider_means_no_route(monkeypatch):
    client, seen = serve(monkeypatch)
    binding.configure(target_binding(not_configured=True))
    assert client.get("/idp/jwks.json").status_code == 404
    assert seen.requests == []


def test_an_idp_that_cannot_be_reached_is_unavailable(monkeypatch):
    client, _ = serve(monkeypatch)
    binding.configure(target_binding(down=True))
    assert client.get("/idp/jwks.json").status_code == 503


def test_a_directory_that_has_no_such_instance_is_a_bad_gateway(monkeypatch):
    class Empty:
        async def forward(self, *args, **kwargs):
            raise RemoteAppUnavailable(404, "App not published by a ready module")

    monkeypatch.setattr(http, "get_remote_app_directory", lambda: Empty())
    app = FastAPI()
    app.add_api_route("/idp/{path:path}", http.serve_idp, methods=http.METHODS)
    response = TestClient(app).get("/idp/jwks.json")
    assert response.status_code == 502
    assert "published" not in response.text  # no detail about the module


# -- which paths ----------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/idp/admin/users",
        "/idp/users",
        "/idp/clients",
        "/idp/keys/rotate",
        "/idp/healthz",
        "/idp/",
        "/idp/authorize/../users",
        "/idp/%2e%2e/users",
        "/idp/login/%2e%2e/%2e%2e/admin",
        "/idp/login%2f..%2fadmin",
        "/idp/login\\..\\admin",
    ],
)
def test_only_the_providers_public_paths_are_served(monkeypatch, path):
    client, seen = serve(monkeypatch)
    assert client.get(path).status_code == 404
    assert client.post(path).status_code in (404, 405)
    assert seen.requests == []


def test_a_path_answers_its_methods_only(monkeypatch):
    client, seen = serve(monkeypatch)
    assert client.post("/idp/jwks.json").status_code == 405
    assert client.get("/idp/token").status_code == 405
    assert client.get("/idp/login/email").status_code == 405
    assert client.delete("/idp/token").status_code == 405
    assert seen.requests == []


# -- request headers, cookies and the client address -----------------------------


def test_the_module_gets_its_cookies_and_not_the_nexus_session(monkeypatch):
    client, seen = serve(monkeypatch)
    response = client.get(
        "/idp/authorize?client_id=abi",
        headers={
            "Cookie": "nexus_session=SECRET; abi_idp_login=rid-1; abi_idp_session=s-1; "
            "abi_app.x=1; abi_idp_bad=a;b",
            "Authorization": "Bearer NEXUS-TOKEN",
            "X-Api-Key": "key",
            "X-Forwarded-For": "6.6.6.6",
            "Origin": "https://evil.example",
            "Accept-Language": "fr",
        },
    )
    assert response.status_code == 200
    headers = dict(seen.requests[0].headers)
    assert headers["cookie"] == "abi_idp_login=rid-1; abi_idp_session=s-1; abi_idp_bad=a"
    assert "nexus_session" not in headers["cookie"]
    names = {k.lower() for k in headers}
    assert names <= {"accept", "accept-language", "content-type", "user-agent", "cookie", "x-abi-client-ip"}
    assert seen.requests[0].query == "client_id=abi"


def test_the_client_address_comes_from_the_connection_never_the_request(monkeypatch):
    client, seen = serve(monkeypatch)
    client.get(
        "/idp/authorize",
        headers={"X-Abi-Client-Ip": "1.2.3.4", "X-Real-Ip": "1.2.3.4", "X-Forwarded-For": "1.2.3.4"},
    )
    headers = dict(seen.requests[0].headers)
    assert headers["x-abi-client-ip"] == "testclient"  # the peer, not what it said


def test_a_clients_credential_goes_to_its_token_endpoints_only(monkeypatch):
    client, seen = serve(monkeypatch)
    auth = {"Authorization": "Basic YWJpOnM=", "Content-Type": "application/x-www-form-urlencoded"}
    client.post("/idp/token", content="grant_type=client_credentials", headers=auth)
    client.post("/idp/revoke", content="token=x", headers=auth)
    client.get("/idp/userinfo", headers={"Authorization": "Bearer t"})
    client.post("/idp/login/email", content="email=a", headers=auth)
    client.get("/idp/authorize", headers={"Authorization": "Bearer t"})
    sent = [any(k == "authorization" for k, _ in r.headers) for r in seen.requests]
    assert sent == [True, True, True, False, False]
    assert seen.requests[0].body == b"grant_type=client_credentials"


def test_large_requests_are_refused(monkeypatch):
    client, seen = serve(monkeypatch)
    assert client.post("/idp/login/email", content=b"x" * (http.MAX_BODY_BYTES + 1)).status_code == 413
    assert client.get("/idp/authorize?" + "a=" + "b" * http.MAX_QUERY_BYTES).status_code == 414
    assert seen.requests == []


def test_no_user_is_passed_on(monkeypatch):
    client, seen = serve(monkeypatch)
    client.get("/idp/authorize", headers={"X-User-Id": "usr_1"})
    assert seen.requests[0].user_id == ""


# -- response headers, cookies and redirects -------------------------------------


def test_the_modules_response_headers_pass_on_an_allow_list(monkeypatch):
    client = answering(
        monkeypatch,
        (
            ("Content-Type", "text/html; charset=utf-8"),
            ("Cache-Control", "no-store"),
            ("Retry-After", "30"),
            ("Content-Security-Policy", "default-src *; script-src 'unsafe-inline'"),
            ("Access-Control-Allow-Origin", "*"),
            ("Strict-Transport-Security", "max-age=0"),
            ("Clear-Site-Data", '"cookies"'),
            ("Refresh", "0; url=https://evil.example"),
            ("X-Frame-Options", "ALLOWALL"),
        ),
    )
    response = client.get("/idp/login")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["retry-after"] == "30"
    for name in ("access-control-allow-origin", "strict-transport-security", "clear-site-data", "refresh"):
        assert name not in response.headers
    assert response.headers["x-frame-options"] == "DENY"


def test_the_policy_is_nexuss_and_stricter_than_the_modules_wish(monkeypatch):
    client = answering(
        monkeypatch,
        (("Content-Type", "text/html"), ("Content-Security-Policy", "default-src *")),
    )
    csp = client.get("/idp/login").headers["content-security-policy"]
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp
    assert "script-src" not in csp and "'unsafe-eval'" not in csp
    assert "default-src *" not in csp
    # A form may post here and to the Nexus origins its sign-in redirects to.
    assert "form-action 'self'" in csp


@pytest.mark.parametrize(
    "cookie, expected",
    [
        ("abi_idp_login=abc; Path=/idp; HttpOnly; SameSite=Lax; Max-Age=900",
         "abi_idp_login=abc; Path=/idp; HttpOnly; SameSite=Lax; Max-Age=900; Secure"),
        ("abi_idp_session=abc; Path=/idp", "abi_idp_session=abc; Path=/idp; HttpOnly; SameSite=Lax; Secure"),
        ("abi_idp_session=; Path=/idp; Max-Age=0", "abi_idp_session=; Path=/idp; HttpOnly; SameSite=Lax; Max-Age=0; Secure"),
        ("abi_idp_session=abc; Path=/idp; SameSite=None", "abi_idp_session=abc; Path=/idp; HttpOnly; SameSite=Lax; Secure"),
        ("abi_idp_login=abc; Path=/idp/login", "abi_idp_login=abc; Path=/idp/login; HttpOnly; SameSite=Lax; Secure"),
        ("nexus_session=abc; Path=/idp", None),
        ("abi_app.x=abc; Path=/idp", None),
        ("abi_idp_login=abc; Path=/", None),
        ("abi_idp_login=abc; Path=/api", None),
        ("abi_idp_login=abc; Path=/idp/../api", None),
        ("abi_idp_login=abc; Path=/idp/%2e%2e/api", None),
        ("abi_idp_login=abc; Path=/idp; Domain=example.com", None),
        ("abi_idp_login=abc", None),
        ("abi_idp_login=a b; Path=/idp", None),
        ("abi_idp_Login=abc; Path=/idp", None),
    ],
)
def test_the_modules_cookies_stay_on_its_path(cookie, expected):
    assert http.module_cookie(cookie, secure=True) == expected


def test_set_cookie_is_not_secure_over_plain_http_and_foreign_cookies_are_dropped(monkeypatch):
    client = answering(
        monkeypatch,
        (
            ("Set-Cookie", "abi_idp_login=abc; Path=/idp; HttpOnly"),
            ("Set-Cookie", "nexus_session=evil; Path=/"),
        ),
    )
    plain = TestClient(client.app, base_url="http://localhost")
    cookies = plain.get("/idp/login").headers.get_list("set-cookie")
    assert cookies == ["abi_idp_login=abc; Path=/idp; HttpOnly; SameSite=Lax"]


@pytest.mark.parametrize(
    "location, kept",
    [
        ("https://abi.example/api/auth/oidc/callback?code=c&state=s", True),
        ("http://localhost:9879/api/auth/oidc/callback?code=c", True),
        ("/idp/login", True),
        ("javascript:alert(1)", False),
        ("data:text/html,x", False),
        ("//evil.example/x", False),
        ("relative/path", False),
        ("https://abi.example/a\\b", False),
        ("https://abi.example/\r\nSet-Cookie: x=y", False),
        ("", False),
    ],
)
def test_a_redirect_is_followed_only_to_a_web_url(monkeypatch, location, kept):
    client = answering(monkeypatch, (("Location", location),), status=302, body=b"")
    response = client.get("/idp/authorize", follow_redirects=False)
    assert response.status_code == 302
    assert ("location" in response.headers) is kept
    if kept:
        assert response.headers["location"] == location


def test_a_streamed_answer_is_refused(monkeypatch):
    async def chunks():
        yield b"x"

    answer = AppResponse(200, (), b"", body_stream=chunks())
    client = serve(monkeypatch, answer)[0]
    assert client.get("/idp/login").status_code == 502


# -- the bound account is the only one that answers ------------------------------


@dataclass
class _App:
    name: str
    contract_major: int = 1
    title: str = ""
    description: str = ""
    category: str = "module"
    icon_emoji: str = ""
    entry: str = "index.html"
    max_upload_bytes: int = 0


@dataclass
class _Instance:
    module_id: str
    service_account: str
    instance_id: str
    apps: tuple = ()
    status: str = "READY"
    contract_major: int = 1


class _Discovery:
    def __init__(self, instances):
        self.instances = instances

    async def list_modules(self, *, limit, after_instance_id):
        return tuple(self.instances), ""


def _real_directory(instances, calls):
    async def call_app(transport, project, instance_id, request, *, service_account=""):
        from naas_abi_proto.app.v1 import app_pb2

        calls.append((instance_id, service_account))
        return app_pb2.HttpResponse(status=200, body=b"{}")

    return DiscoveryRemoteAppDirectory(
        lambda: (_Discovery(instances), object(), object(), "proj"), call_app=call_app
    )


def test_an_instance_of_module_idp_under_another_account_is_never_called():
    idp_apps = (_App("idp"), _App("admin"))
    instances = [
        _Instance("idp", "SA-EVIL", "evil", idp_apps),
        _Instance("idp", "SA-IDP", "good", idp_apps),
    ]
    calls: list = []
    directory = _real_directory(instances, calls)
    for _ in range(8):
        asyncio.run(directory.forward("idp", "idp", AppRequest("GET", "/jwks.json"), service_account="SA-IDP"))
    assert {c[0] for c in calls} == {"good"}
    with pytest.raises(RemoteAppUnavailable):
        asyncio.run(
            directory.forward("idp", "idp", AppRequest("GET", "/jwks.json"), service_account="SA-NOBODY")
        )


def test_the_idp_is_not_in_the_catalog_and_no_generic_route_opens_it():
    idp_apps = (_App("idp"), _App("admin"))
    instances = [
        _Instance("idp", "SA-IDP", "good", idp_apps),
        _Instance("people", "SA-P", "p", (_App("console"),)),
    ]
    directory = _real_directory(instances, [])
    assert [a.module_id for a in asyncio.run(directory.list_apps())] == ["people"]
    with pytest.raises(RemoteAppUnavailable) as refused:
        asyncio.run(directory.forward("idp", "admin", AppRequest("POST", "/users")))
    assert refused.value.status == 404
    memory = InMemoryRemoteAppDirectory({IDP: lambda r: None})  # type: ignore[dict-item]
    assert asyncio.run(memory.list_apps()) == []
    with pytest.raises(RemoteAppUnavailable):
        asyncio.run(memory.forward("idp", "idp", AppRequest("GET", "/")))


# -- the API's middleware leaves the pages alone ---------------------------------


def test_the_api_middleware_does_not_sandbox_or_download_the_login_pages(monkeypatch):
    from naas_abi import ABIModule, NexusConfig

    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main

    page = answering(
        monkeypatch,
        (("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")),
    )
    app = page.app
    app.add_middleware(main.SecurityHeadersMiddleware)
    monkeypatch.setattr(main.settings, "enable_security_headers", True)
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "content_security_policy", None)

    @app.get("/api/user-file")
    def user_file():
        from fastapi.responses import HTMLResponse

        return HTMLResponse("<script>1</script>")

    response = TestClient(app, base_url="https://abi.example").get("/idp/login")
    csp = response.headers["content-security-policy"]
    assert not csp.startswith("sandbox")
    assert "style-src 'unsafe-inline'" in csp  # the global 'self' policy did not merge in
    assert "content-disposition" not in response.headers
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    # Everything else keeps the net: HTML from another route is sandboxed, a download.
    other = TestClient(app).get("/api/user-file")
    assert other.headers["content-security-policy"].startswith("sandbox")
    assert other.headers["content-disposition"].startswith("attachment")


def test_the_trusted_path_is_the_idp_prefix_only():
    assert is_idp_path("/idp") and is_idp_path("/idp/login")
    assert not is_idp_path("/idpx") and not is_idp_path("/api/idp") and not is_idp_path("/app-remote/g/idp/idp/")
