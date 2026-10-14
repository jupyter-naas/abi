from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from jose import jwt
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import http_routes as http
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters.in_memory import (
    InMemoryRemoteAppDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.grant import (
    _key,
    mint_remote_app_grant,
    read_remote_app_grant,
    redact_grant_path,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    AppRequest,
    AppResponse,
    RemoteApp,
    RemoteAppStreamFailed,
)
from naas_abi_core.apps.api.abi_api_key_auth import APP_HTML_TOKEN_COOKIE

CONSOLE = RemoteApp("acme.research", "console")
SECRET = "s3cret-for-tests"


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setattr(http, "current_secret_key", lambda: SECRET)


@pytest.fixture(autouse=True)
def logged_out(monkeypatch) -> dict[str, datetime]:
    """When each user last logged out (revocation.py reads it from the database)."""
    at: dict[str, datetime] = {}

    async def grant_revoked(user_id: str, issued_at: datetime) -> bool:
        return user_id in at and at[user_id] >= issued_at

    monkeypatch.setattr(http.revocation, "grant_revoked", grant_revoked)
    return at


@pytest.fixture(autouse=True)
def workspaces(monkeypatch) -> list[tuple[str, str, str | None]]:
    """The workspace a grant names (access.py checks it in the database):
    the one asked for, else "ws-first"; "ws-off" enables no app."""
    asked: list[tuple[str, str, str | None]] = []

    async def remote_app_workspace(user_id: str, app_id: str, workspace_id: str | None) -> str:
        asked.append((user_id, app_id, workspace_id))
        if workspace_id == "ws-off":
            raise HTTPException(status_code=403, detail="This app is not enabled in this workspace")
        return workspace_id or "ws-first"

    monkeypatch.setattr(http.access, "remote_app_workspace", remote_app_workspace)
    return asked


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
        "/app-html/remote/{module_id}/{app}/{path:path}",
        http.open_remote_app,
        methods=http.METHODS,
    )
    app.add_api_route(
        "/app-html/remote/{module_id}/{app}", http.open_remote_app, methods=http.METHODS
    )
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


def _presenting(monkeypatch, user_id: str, minutes_left: float | None = 60) -> None:
    expires = None if minutes_left is None else datetime.now(UTC) + timedelta(minutes=minutes_left)
    monkeypatch.setattr(http, "_presented_user", lambda request: (user_id, expires))


def _grant_of(response) -> tuple[str, str, dict]:
    _, prefix, grant, rest = response.headers["location"].split("/", 3)
    claims = jwt.get_unverified_claims(grant)
    return prefix, rest, {"grant": grant, **claims}


def test_the_catalog_url_redirects_to_a_fresh_grant(monkeypatch, forwarded, workspaces):
    _presenting(monkeypatch, "u-7")

    response = _client().get(
        "/app-html/remote/acme.research/console/index.html?token=jwt&q=1", follow_redirects=False
    )

    assert response.status_code == 307
    prefix, rest, claims = _grant_of(response)
    assert (prefix, rest) == ("app-remote", "acme.research/console/index.html?q=1")
    granted = read_remote_app_grant(claims["grant"], secret=SECRET)
    assert granted is not None
    assert (granted.user_id, granted.module_id, granted.app) == ("u-7", "acme.research", "console")
    # A15: an old link names no workspace: the first of the user's that enables it.
    assert granted.workspace_id == "ws-first"
    assert workspaces == [("u-7", "remote/acme.research:console", None)]


def test_a_grant_never_outlives_the_credential_it_was_exchanged_for(monkeypatch, forwarded):
    _presenting(monkeypatch, "u-7", minutes_left=1)  # a share link opened at its last minute

    response = _client().get("/app-html/remote/acme.research/console/", follow_redirects=False)

    _, _, claims = _grant_of(response)
    assert claims["exp"] <= (datetime.now(UTC) + timedelta(minutes=1)).timestamp() + 1


def test_an_api_key_caller_is_answered_without_a_grant(monkeypatch, forwarded):
    """A script with ABI_API_KEY has no user and no browser: no grant, the
    module answers it directly, with no user and no workspace, any method."""
    _presenting(monkeypatch, "", minutes_left=None)  # ABI_API_KEY

    client = _client()
    response = client.post(
        "/app-html/remote/acme.research/console/api/save?q=1",
        content=b'{"a": 1}',
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["content-security-policy"] == http.SANDBOX
    (request,) = forwarded
    assert (request.method, request.path, request.query) == ("POST", "/api/save", "q=1")
    assert (request.user_id, request.workspace_id, request.body) == ("", "", b'{"a": 1}')
    assert request.root_path == "/app-html/remote/acme.research/console"


def test_a_grant_is_minted_and_read_for_a_user_only():
    with pytest.raises(ValueError):
        mint_remote_app_grant(secret=SECRET, user_id="", module_id="acme.research", app="console")
    anonymous = jwt.encode(
        {
            "scope": "app-remote",
            "uid": "",
            "mod": "acme.research",
            "app": "console",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        _key(SECRET),
        algorithm="HS256",
    )
    assert read_remote_app_grant(anonymous, secret=SECRET) is None


@pytest.mark.parametrize(
    "path",
    [
        "/app-html/remote/acme%3Fx/console/",
        "/app-html/remote/acme.research/con%3Fsole/",
        "/app-html/remote/acme.research/con%23sole/",
        "/app-html/remote/acme.research/con.sole/",
    ],
)
def test_the_catalog_url_names_one_module_and_one_app(monkeypatch, forwarded, path):
    _presenting(monkeypatch, "u-7")

    response = _client().get(path, follow_redirects=False)

    assert response.status_code == 404
    assert "location" not in response.headers


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

    monkeypatch.setattr(main.settings, "frontend_url", "https://nexus.example")
    framer = {"Origin": "https://evil.example", "Referer": "https://other.example/page"}

    response = TestClient(app).get(f"{ROOT}/", headers=framer)

    assert response.headers["referrer-policy"] == "no-referrer"
    csp = response.headers["content-security-policy"]
    assert csp.startswith(f"{http.SANDBOX}; frame-ancestors ")
    assert "https://nexus.example" in csp
    # Only Nexus frames a remote app, whoever asks.
    assert "evil.example" not in csp and "other.example" not in csp
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
        ("%2e%2e/%2e%2e/%2e%2e/%2e%2e/api/auth/me", None),
        ("%2E%2E/%2E%2E/%2E%2E/%2E%2E/api/auth/me", None),
        ("..\\..\\..\\..\\api\\auth\\me", None),
        ("/\\evil.example/", None),
        ("%5c%5cevil.example/", None),
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
            ("Set-Cookie", f"dots=1; Path={ROOT}/%2e%2e/%2e%2e/%2e%2e/%2e%2e/"),
            ("Set-Cookie", f"slash=1; Path={ROOT}/..\\..\\..\\..\\"),
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
    uploads = http._Slots(http.MAX_UPLOADS_PER_MODULE, "busy")
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


def test_the_user_and_expiry_come_from_the_nexus_token(monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.auth import service

    monkeypatch.setattr(
        service,
        "decode_token",
        lambda token: {"sub": "u-7", "exp": 1_900_000_000} if token == "jwt" else None,
    )
    request = type("R", (), {})()

    monkeypatch.setattr(http, "extract_abi_api_token", lambda r: "jwt")
    assert http._presented_user(request) == ("u-7", datetime.fromtimestamp(1_900_000_000, UTC))
    monkeypatch.setattr(http, "extract_abi_api_token", lambda r: "abi-api-key")
    assert http._presented_user(request) == ("", None)


# -- the grant is a credential: never in logs or traces ------------------------


def test_the_grant_is_redacted_from_paths():
    assert redact_grant_path(f"{ROOT}/api/x") == "/app-remote/[grant]/acme.research/console/api/x"
    assert redact_grant_path("/api/apps") == "/api/apps"
    assert redact_grant_path("/app-html/remote/acme/console/") == "/app-html/remote/acme/console/"


def test_the_access_log_hides_the_grant():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1", "GET", f"{ROOT}/index.html?x=1", "1.1", 200),
        None,
    )

    assert http.RedactGrantFilter().filter(record)

    assert GRANT not in record.getMessage()
    assert "/app-remote/[grant]/acme.research/console/index.html?x=1" in record.getMessage()


# -- #48 review: grants end at logout, and name a workspace -----------------------


def test_a_logout_ends_the_grants_issued_before_it(monkeypatch, forwarded, logged_out):
    client = _client()
    assert client.get(f"{ROOT}/").status_code == 200

    logged_out["u-42"] = datetime.now(UTC)

    for response in (
        client.get(f"{ROOT}/"),
        client.post(f"{ROOT}/api/save", content=b"{}"),
        client.get(ROOT, follow_redirects=False),
    ):
        assert response.status_code == 401
        assert response.headers["content-security-policy"] == http.SANDBOX
    fresh = f"/app-remote/{_grant()}/acme.research/console"
    assert client.get(f"{fresh}/").status_code == 200


def test_the_module_learns_the_workspace_of_the_grant(forwarded):
    grant = mint_remote_app_grant(
        secret=SECRET,
        user_id="u-42",
        module_id="acme.research",
        app="console",
        workspace_id="ws-9",
    )

    _client().get(f"/app-remote/{grant}/acme.research/console/")

    assert (forwarded[0].user_id, forwarded[0].workspace_id) == ("u-42", "ws-9")


def test_the_catalog_url_opens_the_workspace_it_names(monkeypatch, forwarded, workspaces):
    _presenting(monkeypatch, "u-7")
    client = _client()

    response = client.get(
        "/app-html/remote/acme.research/console/?workspace_id=ws-2&q=1", follow_redirects=False
    )

    _, rest, claims = _grant_of(response)
    assert claims["ws"] == "ws-2"
    assert rest == "acme.research/console/?q=1"  # Nexus's parameter stays with Nexus
    refused = client.get(
        "/app-html/remote/acme.research/console/?workspace_id=ws-off", follow_redirects=False
    )
    assert refused.status_code == 403
    assert "location" not in refused.headers


def test_a_post_to_the_catalog_url_keeps_its_method(monkeypatch, forwarded):
    """The catalog route takes every method; a 307 keeps the method and body."""
    _presenting(monkeypatch, "u-7")

    response = _client().post(
        "/app-html/remote/acme.research/console/api/save", content=b"{}", follow_redirects=False
    )

    assert response.status_code == 307
    assert response.headers["location"].endswith("/acme.research/console/api/save")


def test_a_grant_without_its_issue_time_is_refused(forwarded):
    """Grants from before revocation existed cannot be checked: open the app again."""
    old = jwt.encode(
        {
            "scope": "app-remote",
            "uid": "u-42",
            "mod": "acme.research",
            "app": "console",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        _key(SECRET),
        algorithm="HS256",
    )

    response = _client().get(f"/app-remote/{old}/acme.research/console/")

    assert response.status_code == 401


# -- #48 review: the response headers an app's API needs ---------------------------


def test_an_apis_response_headers_reach_the_page(monkeypatch):
    _answering(
        monkeypatch,
        (
            ("X-Request-Id", "r-1"),
            ("X-RateLimit-Remaining", "9"),
            ("Retry-After", "30"),
            ("WWW-Authenticate", 'Bearer realm="app"'),
            ("Link", '<page/2>; rel="next"'),
            ("Location", "items/5"),
            ("X-Accel-Redirect", "/internal/secrets"),
            ("X-Sendfile", "/etc/passwd"),
            ("X-Forwarded-Host", "evil.example"),
        ),
        status=201,
    )

    response = _client().post(f"{ROOT}/api/items", content=b"{}")

    assert response.status_code == 201
    assert response.headers["x-request-id"] == "r-1"
    assert response.headers["x-ratelimit-remaining"] == "9"
    assert response.headers["retry-after"] == "30"
    assert response.headers["www-authenticate"] == 'Bearer realm="app"'
    assert response.headers["link"] == '<page/2>; rel="next"'
    assert response.headers["location"] == f"{ROOT}/api/items/5"
    for dropped in ("x-accel-redirect", "x-sendfile", "x-forwarded-host"):
        assert dropped not in response.headers, dropped
    # The page's fetch() is cross-origin: it may read them.
    assert response.headers["access-control-expose-headers"] == "*"


def test_headers_http_cannot_carry_are_dropped(monkeypatch):
    """A23: a module's header value with a line break or outside latin-1 is
    dropped, not a 500."""
    _answering(
        monkeypatch,
        (
            ("X-Label", "café ☕"),
            ("X-Split", "a\r\nSet-Cookie: abi_app_html_token=x"),
            ("X Bad Name", "1"),
            ("X-Fine", "ok"),
        ),
    )

    response = _client().get(f"{ROOT}/")

    assert response.status_code == 200
    assert response.headers["x-fine"] == "ok"
    for dropped in ("x-label", "x-split", "set-cookie"):
        assert dropped not in response.headers, dropped


# -- #48 security review: cookie pairs and the joined request path ------------------


def test_a_cookie_is_cut_at_its_first_semicolon_and_needs_a_name(monkeypatch):
    _answering(
        monkeypatch,
        (
            ("Set-Cookie", f"flag; Path={ROOT}/; x=y"),
            ("Set-Cookie", f"bad name=1; Path={ROOT}/"),
            ("Set-Cookie", f"=anonymous; Path={ROOT}/"),
            ("Set-Cookie", f"theme=a=b; Path={ROOT}/; Secure"),
        ),
    )

    response = _client().get(f"{ROOT}/")

    assert response.headers.get_list("set-cookie") == [
        f"{http.APP_COOKIE_PREFIX}theme=a=b; Path={ROOT}/; Secure"
    ]


def test_a_relative_redirect_from_a_dot_segment_path_is_dropped(monkeypatch):
    """`%252e%252e` reaches the route as `%2e%2e`: joined to a relative
    Location, the browser would read it as `..` and leave the app."""
    _answering(monkeypatch, (("Location", "next"),), status=302)
    client = _client()

    escaped = client.get(f"{ROOT}/%252e%252e/%252e%252e/%252e%252e/x", follow_redirects=False)
    plain = client.get(f"{ROOT}/api/x", follow_redirects=False)

    assert "location" not in escaped.headers
    assert plain.headers["location"] == f"{ROOT}/api/next"


# -- A6, A23, A27, A29: bodies and queries pass as they are -------------------------


def test_the_query_reaches_the_module_as_the_browser_sent_it(forwarded):
    """A27: no re-encoding; only the access token is taken out."""
    _client().get(f"{ROOT}/api/x?a=b%20c&flag&token=jwt&path=%2Fdocs&sig=x%2By&a=2")

    assert forwarded[0].query == "a=b%20c&flag&path=%2Fdocs&sig=x%2By&a=2"


def test_head_carries_the_length_get_would_send(monkeypatch):
    _answering(monkeypatch, (("Content-Length", "1234"), ("Content-Type", "text/plain")))

    async def head(request: AppRequest) -> AppResponse:
        return AppResponse(200, (("Content-Length", "1234"),), b"")

    _directory(monkeypatch, head)

    response = _client().head(f"{ROOT}/report.txt")

    assert response.headers["content-length"] == "1234"


class _Body:
    """A module's streamed body as the directory hands it over: closing it,
    started or not, tells the module (discovery adapter: _Pulled)."""

    def __init__(self, chunks, fail, closed):
        self.chunks, self.fail, self.closed = list(chunks), fail, closed

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.chunks:
            return self.chunks.pop(0)
        if self.fail:
            raise RemoteAppStreamFailed("the module's app failed")
        raise StopAsyncIteration

    async def aclose(self):
        if self.closed is not None:
            self.closed.append(True)


def _streaming(monkeypatch, chunks, *, length=None, fail=False, closed=None):
    async def answer(request: AppRequest) -> AppResponse:
        headers = () if length is None else (("Content-Length", str(length)),)
        return AppResponse(200, headers, body_stream=_Body(chunks, fail, closed))

    _directory(monkeypatch, answer)


def test_a_streamed_answer_carries_the_apps_length(monkeypatch):
    _streaming(monkeypatch, [b"ab", b"cd"], length=4)

    response = _client().get(f"{ROOT}/file.bin")

    assert response.content == b"abcd"
    assert response.headers["content-length"] == "4"
    assert "transfer-encoding" not in response.headers


def test_a_stream_that_breaks_off_fails_in_the_browser(monkeypatch):
    """A6: the connection is aborted; a short body never looks whole."""
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    app = _client().app
    for length in (None, 6):
        _streaming(monkeypatch, [b"abc"], length=length, fail=True)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="critical")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(0.02)
            with pytest.raises(httpx.RemoteProtocolError):
                httpx.get(f"http://127.0.0.1:{port}{ROOT}/file.bin", timeout=5)
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def test_one_modules_streams_are_capped_per_worker(monkeypatch):
    """A29: a module's open streams cannot take every worker slot; above the
    cap the stream is closed (the module stops its app) and the browser gets 503."""
    closed: list[bool] = []
    _streaming(monkeypatch, [b"x"], closed=closed)
    monkeypatch.setattr(http, "_streams", http._Slots(1, "Too many responses streaming"))
    release = http._streams.acquire("acme.research")

    refused = _client().get(f"{ROOT}/events")

    assert refused.status_code == 503
    assert refused.headers["content-security-policy"] == http.SANDBOX
    assert closed == [True]
    release()
    assert _client().get(f"{ROOT}/events").content == b"x"
    assert http._streams.active == {}


def test_a_stream_stops_when_the_browser_leaves_while_it_is_idle():
    """A22: no event to send, the browser leaves: the body is closed now."""
    import asyncio

    async def scenario():
        closed = asyncio.Event()

        async def idle():
            try:
                yield b"data: hello\n\n"
                await asyncio.sleep(3600)
            finally:
                closed.set()

        released = []
        response = http._RemoteAppStream(idle(), lambda: released.append(True), 200)
        sent: list[dict] = []
        left = asyncio.Event()

        async def receive():
            await left.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "asgi": {"spec_version": "2.4"}}
        serving = asyncio.create_task(response(scope, receive, send))
        while len(sent) < 2:
            await asyncio.sleep(0.01)
        left.set()
        await asyncio.wait_for(serving, 1)
        assert closed.is_set() and released == [True]

    asyncio.run(scenario())
