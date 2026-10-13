from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import http_routes as http
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters.in_memory import (
    InMemoryRemoteAppDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.grant import (
    RemoteAppGrant,
    mint_remote_app_grant,
    read_remote_app_grant,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    AppRequest,
    AppResponse,
    RemoteApp,
)
from naas_abi_core.apps.api.abi_api_key_auth import APP_HTML_TOKEN_COOKIE

CONSOLE = RemoteApp("acme.research", "console")
SECRET = "s3cret-for-tests"


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setattr(http, "current_secret_key", lambda: SECRET)


def _grant(module_id: str = "acme.research", app: str = "console", user_id: str = "u-42") -> str:
    return mint_remote_app_grant(secret=SECRET, user_id=user_id, module_id=module_id, app=app)


GRANT = _grant()
ROOT = f"/app-remote/{GRANT}/acme.research/console"


def _directory(monkeypatch, handler, app: RemoteApp = CONSOLE) -> None:
    directory = InMemoryRemoteAppDirectory({app: handler})
    monkeypatch.setattr(http, "get_remote_app_directory", lambda: directory)


@pytest.fixture
def forwarded(monkeypatch):
    seen: list[AppRequest] = []

    async def answer(request: AppRequest) -> AppResponse:
        seen.append(request)
        return AppResponse(200, (("content-type", "application/json"),), b'{"ok": true}')

    _directory(monkeypatch, answer)
    return seen


def _answering(monkeypatch, headers: tuple[tuple[str, str], ...], status: int = 200) -> None:
    async def answer(request: AppRequest) -> AppResponse:
        return AppResponse(status, headers, b"ok")

    _directory(monkeypatch, answer)


def _client() -> TestClient:
    app = FastAPI()
    app.add_api_route(
        "/app-html/remote/{module_id}/{app}/{path:path}", http.open_remote_app, methods=["GET"]
    )
    app.add_api_route("/app-html/remote/{module_id}/{app}", http.open_remote_app, methods=["GET"])
    app.add_api_route(
        "/app-remote/{grant}/{module_id}/{app}/{path:path}",
        http.serve_remote_app,
        methods=http.METHODS,
    )
    app.add_api_route(
        "/app-remote/{grant}/{module_id}/{app}", http.redirect_remote_app_root, methods=["GET"]
    )
    return TestClient(app)


# -- A1: the page runs sandboxed, and the grant is its only credential ----------


def test_every_remote_app_response_is_sandboxed(forwarded):
    client = _client()

    responses = {
        200: client.get(f"{ROOT}/"),
        401: client.get(f"/app-remote/{GRANT}/acme.research/other/"),  # another app's
        404: client.get(f"/app-remote/{_grant(app='other')}/acme.research/other/"),
    }

    for status, response in responses.items():
        assert response.status_code == status
        assert response.headers["content-security-policy"] == http.SANDBOX
        assert "allow-same-origin" not in response.headers["content-security-policy"]
        assert response.headers["referrer-policy"] == "no-referrer"


def test_the_modules_own_policy_does_not_replace_the_sandbox(monkeypatch):
    _answering(
        monkeypatch,
        (
            ("Content-Security-Policy", "default-src *"),
            ("Referrer-Policy", "unsafe-url"),
        ),
    )

    response = _client().get(f"{ROOT}/")

    assert response.headers.get_list("content-security-policy") == [http.SANDBOX]
    assert response.headers.get_list("referrer-policy") == ["no-referrer"]


def test_the_grant_opens_its_own_app_only(forwarded):
    from naas_abi.apps.nexus.apps.api.app.services.auth import service as auth_service

    client = _client()
    session, _ = auth_service.create_access_token({"sub": "u-42"})

    assert client.get("/app-remote/forged/acme.research/console/").status_code == 401
    assert client.get(f"/app-remote/{session}/acme.research/console/").status_code == 401
    assert client.get(f"/app-remote/{GRANT}/acme.other/console/").status_code == 401
    assert client.get(f"{ROOT}/").status_code == 200
    assert forwarded[0].user_id == "u-42"
    assert forwarded[0].root_path == ROOT


def test_a_grant_is_never_a_session_token(monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.auth import service as auth_service

    monkeypatch.setattr(auth_service.settings, "secret_key", SECRET)
    assert auth_service.decode_token(GRANT) is None
    session, _ = auth_service.create_access_token(
        {"sub": "u-42", "scope": "app-remote", "uid": "u-42", "mod": "acme.research", "app": "x"}
    )
    assert read_remote_app_grant(session, secret=SECRET) is None


def test_the_catalog_url_redirects_to_a_fresh_grant(monkeypatch, forwarded):
    monkeypatch.setattr(http, "_user_id", lambda request: "u-7")

    response = _client().get(
        "/app-html/remote/acme.research/console/index.html?token=jwt&q=1", follow_redirects=False
    )

    assert response.status_code == 307
    _, prefix, grant, rest = response.headers["location"].split("/", 3)
    assert (prefix, rest) == ("app-remote", "acme.research/console/index.html?q=1")
    assert read_remote_app_grant(grant, secret=SECRET) == RemoteAppGrant(
        "u-7", "acme.research", "console"
    )


def test_the_app_root_redirects_to_its_folder(forwarded):
    response = _client().get(f"{ROOT}?x=1", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].endswith(f"{ROOT}/?x=1")


def test_preflights_from_the_sandbox_are_answered_before_cors():
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["https://nexus.example"])
    app.add_middleware(http.RemoteAppPreflight)
    client = TestClient(app)
    preflight = {
        "Origin": "null",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type, x-app-version",
    }

    response = client.options(f"{ROOT}/api/save", headers=preflight)

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-headers"] == "content-type, x-app-version"
    assert "access-control-allow-credentials" not in response.headers
    # Elsewhere the API's CORS policy still decides.
    assert client.options("/api/apps", headers=preflight).status_code == 400


def test_the_api_middleware_keeps_the_sandbox_and_no_referrer(monkeypatch, forwarded):
    from naas_abi import ABIModule, NexusConfig

    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main

    app = _client().app
    app.add_middleware(main.SecurityHeadersMiddleware)
    monkeypatch.setattr(main.settings, "enable_security_headers", True)

    response = TestClient(app).get(f"{ROOT}/", headers={"Origin": "https://nexus.example"})

    assert response.headers["referrer-policy"] == "no-referrer"
    csp = response.headers["content-security-policy"]
    assert csp.startswith(f"{http.SANDBOX}; frame-ancestors ")
    assert "https://nexus.example" in csp
    assert "x-frame-options" not in response.headers
    # A sandboxed page's fetch() sends "Origin: null": no bogus ancestor.
    from_sandbox = TestClient(app).get(f"{ROOT}/api/report", headers={"Origin": "null"})
    assert " :" not in from_sandbox.headers["content-security-policy"]


# -- A2: only an allow-list of response headers reaches the browser -------------


def test_only_allowed_response_headers_reach_the_browser(monkeypatch):
    _answering(
        monkeypatch,
        (
            ("Content-Type", "text/html"),
            ("ETag", '"v1"'),
            ("Cache-Control", "no-cache"),
            ("Clear-Site-Data", '"storage"'),
            ("Access-Control-Allow-Origin", "https://evil.example"),
            ("Access-Control-Allow-Credentials", "true"),
            ("Strict-Transport-Security", "max-age=0"),
            ("X-Frame-Options", "ALLOWALL"),
            ("Transfer-Encoding", "chunked"),
            ("Refresh", "0; url=https://evil.example"),
        ),
    )

    response = _client().get(f"{ROOT}/")

    assert response.headers["content-type"] == "text/html"
    assert response.headers["etag"] == '"v1"'
    assert response.headers["cache-control"] == "no-cache"
    for dropped in (
        "clear-site-data",
        "strict-transport-security",
        "x-frame-options",
        "access-control-allow-credentials",
        "transfer-encoding",
        "refresh",
    ):
        assert dropped not in response.headers, dropped
    assert response.headers["access-control-allow-origin"] == "*"


@pytest.mark.parametrize(
    ("location", "kept"),
    [
        ("done", f"{ROOT}/api/done"),
        ("../index.html?x=1", f"{ROOT}/index.html?x=1"),
        (f"{ROOT}/login", f"{ROOT}/login"),
        ("https://evil.example/", None),
        ("//evil.example/", None),
        ("/api/auth/logout", None),
        ("../../../other/console/", None),
        (f"/app-remote/{_grant(app='other')}/acme.research/other/", None),
    ],
)
def test_a_redirect_stays_in_the_app(monkeypatch, location, kept):
    _answering(monkeypatch, (("Location", location),), status=302)

    response = _client().post(f"{ROOT}/api/save", follow_redirects=False)

    assert response.headers.get("location") == kept


def test_only_the_apps_own_cookies_are_set(monkeypatch):
    _answering(
        monkeypatch,
        (
            ("Set-Cookie", "everywhere=1; Path=/"),
            ("Set-Cookie", "nopath=1"),
            ("Set-Cookie", f"domain=1; Path={ROOT}/; Domain=example.com"),
            ("Set-Cookie", f"{APP_HTML_TOKEN_COOKIE}=stolen; Path={ROOT}/"),
            ("Set-Cookie", "sibling=1; Path=/app-remote/x/acme.research/console-2/"),
            ("Set-Cookie", f"sid=abc; Path={ROOT}/; HttpOnly; SameSite=None; Secure"),
            ("Set-Cookie", f"pref=dark; path={ROOT}"),
        ),
    )

    response = _client().get(f"{ROOT}/")

    assert response.headers.get_list("set-cookie") == [
        f"{http.APP_COOKIE_PREFIX}sid=abc; Path={ROOT}/; HttpOnly; SameSite=None; Secure",
        f"{http.APP_COOKIE_PREFIX}pref=dark; path={ROOT}",
    ]


# -- A3: only an allow-list of request headers reaches the module ---------------


def test_requests_reach_the_module_without_the_users_credentials(forwarded):
    client = _client()
    client.cookies.set(APP_HTML_TOKEN_COOKIE, "jwt")
    client.cookies.set("nexus_session", "secret")
    client.cookies.set(f"{http.APP_COOKIE_PREFIX}sid", "abc")

    response = client.post(
        f"{ROOT}/api/save?token=jwt&q=1",
        content=b'{"a": 1}',
        headers={
            "Authorization": "Bearer jwt",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Language": "fr",
            "Accept-Encoding": "gzip",
            "If-None-Match": '"v1"',
            "Range": "bytes=0-9",
            "User-Agent": "browser",
            "X-App-Version": "3",
            "X-Forwarded-For": "10.0.0.1",
            "X-Real-IP": "10.0.0.1",
            "X-Api-Key": "key",
            "Origin": "null",
            "Referer": f"https://api.example{ROOT}/index.html?token=jwt",
        },
    )

    assert response.status_code == 200 and response.json() == {"ok": True}
    (sent,) = forwarded
    assert (sent.method, sent.path, sent.query, sent.body, sent.user_id) == (
        "POST",
        "/api/save",
        "q=1",
        b'{"a": 1}',
        "u-42",
    )
    assert dict(sent.headers) == {
        "content-type": "application/json",
        "accept": "application/json",
        "accept-language": "fr",
        "accept-encoding": "gzip",
        "if-none-match": '"v1"',
        "range": "bytes=0-9",
        "user-agent": "browser",
        "x-app-version": "3",
        "cookie": "sid=abc",
    }


# -- forwarding ------------------------------------------------------------------


def test_unknown_apps_are_404(monkeypatch, forwarded):
    response = _client().get(f"/app-remote/{_grant(app='other')}/acme.research/other/")

    assert response.status_code == 404


def test_an_upload_above_the_apps_limit_is_refused(monkeypatch):
    small = RemoteApp("acme.research", "console", max_upload_bytes=1000)

    async def never(request):
        raise AssertionError("not forwarded")

    _directory(monkeypatch, never, small)

    response = _client().put(f"{ROOT}/f", content=b"x" * 1001)

    assert response.status_code == 413
    assert response.headers["content-security-policy"] == http.SANDBOX


def test_a_large_upload_streams_and_a_small_one_is_inline(monkeypatch):
    received = []

    async def handler(request: AppRequest) -> AppResponse:
        if request.body_stream is None:
            received.append(("inline", len(request.body)))
        else:
            size = sum([len(c) async for c in request.body_stream])
            received.append(("stream", size, request.max_body_bytes))
        return AppResponse(200, (), b"ok")

    _directory(monkeypatch, handler)
    client = _client()

    assert client.put(f"{ROOT}/f", content=b"x" * 1000).status_code == 200
    big = b"y" * (3 * 1024 * 1024)
    assert client.put(f"{ROOT}/f", content=big).status_code == 200

    assert received == [("inline", 1000), ("stream", len(big), CONSOLE.upload_limit)]


def test_a_streamed_answer_reaches_the_browser(monkeypatch):
    async def handler(request: AppRequest) -> AppResponse:
        async def events():
            for index in range(3):
                yield f"data: {index}\n\n".encode()

        return AppResponse(200, (("content-type", "text/event-stream"),), body_stream=events())

    _directory(monkeypatch, handler)

    response = _client().get(f"{ROOT}/events")

    assert response.headers["content-type"] == "text/event-stream"
    assert response.headers["content-security-policy"] == http.SANDBOX
    assert response.text == "data: 0\n\ndata: 1\n\ndata: 2\n\n"


def test_uploads_to_one_module_are_capped():
    uploads = http._Uploads()
    slots = [uploads.slot("m") for _ in range(http.MAX_UPLOADS_PER_MODULE)]
    for slot in slots:
        slot.__enter__()
    with pytest.raises(http.HTTPException) as refused, uploads.slot("m"):
        pass
    assert refused.value.status_code == 503
    with uploads.slot("other"):
        pass
    for slot in slots:
        slot.__exit__(None, None, None)
    assert uploads.active == {}


def test_the_user_comes_from_the_nexus_token(monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.auth import service

    monkeypatch.setattr(
        service, "decode_token", lambda token: {"sub": "u-7"} if token == "jwt" else None
    )
    request = type("R", (), {})()

    monkeypatch.setattr(http, "extract_abi_api_token", lambda r: "jwt")
    assert http._user_id(request) == "u-7"
    monkeypatch.setattr(http, "extract_abi_api_token", lambda r: "abi-api-key")
    assert http._user_id(request) == ""
