from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
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
    redact_grant_path,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    AppRequest,
    AppResponse,
    RemoteApp,
)
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi_core.apps.api.abi_api_key_auth import APP_HTML_TOKEN_COOKIE
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService

CONSOLE = RemoteApp("acme.research", "console")

# The engine's IAM, where grants live: one for this module's tests.
IAM = IAMService(IAMStoreMemory())
IAM.bootstrap()


@pytest.fixture(autouse=True)
def engine_iam():
    previous = credentials.configure_iam(lambda: IAM)
    yield IAM
    credentials.configure_iam(previous)


def _grant(module_id: str = "acme.research", app: str = "console", user_id: str = "u-42") -> str:
    # Also called while the module loads (parameters), before any fixture ran.
    previous = credentials.configure_iam(lambda: IAM)
    try:
        return mint_remote_app_grant(user_id=user_id, module_id=module_id, app=app)
    finally:
        credentials.configure_iam(previous)


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
    from jose import jwt

    client = _client()
    session = jwt.encode(
        {"sub": "u-42", "aud": "abi:session", "jti": "j"},
        "the-key-nexus-used-to-sign-with",
        algorithm="HS256",
    )

    assert client.get("/app-remote/forged/acme.research/console/").status_code == 401
    assert client.get(f"/app-remote/{session}/acme.research/console/").status_code == 401
    assert client.get(f"/app-remote/{GRANT}/acme.other/console/").status_code == 401
    assert client.get(f"{ROOT}/").status_code == 200
    assert forwarded[0].user_id == "u-42"
    assert forwarded[0].root_path == ROOT


def test_a_grant_is_never_a_session_token(monkeypatch):
    import asyncio

    from jose import jwt

    assert asyncio.run(credentials.bearer_credential(GRANT)) is None
    old = jwt.encode(
        {"sub": "u-42", "scope": "app-remote", "uid": "u-42", "mod": "acme.research", "app": "x"},
        "the-key-nexus-used-to-sign-with",
        algorithm="HS256",
    )
    assert read_remote_app_grant(old) is None
    # Nor does it act as one at the API: its audience is its own.
    assert credentials.accepted_kinds("/api/chat") == {"session", "api-key"}


def _presenting(monkeypatch, user_id: str, minutes_left: float | None = 60) -> None:
    expires = None if minutes_left is None else datetime.now(UTC) + timedelta(minutes=minutes_left)

    async def presented(request):
        return user_id, expires

    monkeypatch.setattr(http, "_presented_user", presented)


def _grant_of(response) -> tuple[str, str, dict]:
    _, prefix, grant, rest = response.headers["location"].split("/", 3)
    key_id = grant.split("_")[2]
    record = IAM.store.get_key(key_id)
    return prefix, rest, {"grant": grant, "key": record, "exp": record.expires_at.timestamp()}


def test_the_catalog_url_redirects_to_a_fresh_grant(monkeypatch, forwarded):
    _presenting(monkeypatch, "u-7")

    response = _client().get(
        "/app-html/remote/acme.research/console/index.html?token=jwt&q=1", follow_redirects=False
    )

    assert response.status_code == 307
    prefix, rest, claims = _grant_of(response)
    assert (prefix, rest) == ("app-remote", "acme.research/console/index.html?q=1")
    assert read_remote_app_grant(claims["grant"]) == RemoteAppGrant(
        "u-7", "acme.research", "console", read_remote_app_grant(claims["grant"]).scope
    )
    # It opens this app and does nothing else at the kernel.
    scope = read_remote_app_grant(claims["grant"]).scope
    assert scope is not None and scope[0]["actions"] == ["discovery:OpenApp"]
    assert scope[0]["resources"] == ["abi:-:-:discovery:app/*/acme.research/console"]
    # IAM keeps it hashed: eight hours at most.
    assert claims["key"].kind == "grant" and claims["key"].audience == "abi:delegated:app"
    assert claims["exp"] <= (datetime.now(UTC) + timedelta(hours=8)).timestamp() + 1


def test_a_grant_never_outlives_the_credential_it_was_exchanged_for(monkeypatch, forwarded):
    _presenting(monkeypatch, "u-7", minutes_left=1)  # a share link opened at its last minute

    response = _client().get("/app-html/remote/acme.research/console/", follow_redirects=False)

    _, _, claims = _grant_of(response)
    assert claims["exp"] <= (datetime.now(UTC) + timedelta(minutes=1)).timestamp() + 1


def test_a_revoked_grant_stops_at_the_next_request(forwarded):
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )

    client = _client()
    grant = _grant(user_id="u-revoked")
    root = f"/app-remote/{grant}/acme.research/console"
    assert client.get(f"{root}/").status_code == 200
    with use_call_context(
        CallContext(principal=service_account("api"), on_behalf_of=user("u-revoked"))
    ):
        IAM.revoke_key("u-revoked", grant.split("_")[2])
    assert client.get(f"{root}/").status_code == 401


def test_a_suspended_user_s_grant_stops_too(forwarded):
    from naas_abi_core.engine.call_context import as_service_account

    client = _client()
    grant = _grant(user_id="u-suspended")
    root = f"/app-remote/{grant}/acme.research/console"
    assert client.get(f"{root}/").status_code == 200
    with as_service_account("engine"):
        record = IAM.resolve_user("u-suspended")
        IAM.suspend_principal(record.id)
    assert client.get(f"{root}/").status_code == 401


def test_the_request_is_forwarded_for_the_grants_user_narrowed_to_opening_the_app(
    monkeypatch,
):
    from naas_abi_core.engine.call_context import current_call_context

    seen = []

    async def answer(request: AppRequest) -> AppResponse:
        seen.append(current_call_context())
        return AppResponse(200, (), b"ok")

    _directory(monkeypatch, answer)
    assert _client().get(f"{ROOT}/").status_code == 200
    [context] = seen
    assert context.principal.id == "api"
    assert context.on_behalf_of is not None and context.on_behalf_of.id == "u-42"
    assert context.scope is not None
    assert context.scope[0]["actions"] == ["discovery:OpenApp"]


def test_the_catalog_url_needs_a_user(monkeypatch, forwarded):
    _presenting(monkeypatch, "", minutes_left=None)  # ABI_API_KEY

    response = _client().get("/app-html/remote/acme.research/console/", follow_redirects=False)

    assert response.status_code == 403
    assert "location" not in response.headers


def test_a_grant_is_minted_and_read_for_a_user_and_an_app_only():
    from naas_abi.apps.nexus.apps.api.app.services.apps import links
    from naas_abi_core.engine.nats_auth import PREVIEW_AUDIENCE

    with pytest.raises(ValueError):
        mint_remote_app_grant(user_id="", module_id="acme.research", app="console")
    with pytest.raises(ValueError):
        mint_remote_app_grant(user_id="u-1", module_id="acme/research", app="console")
    # A preview link, or a link bound to anything else, is no remote app grant.
    preview, _ = links.mint_link(
        user_id="u-1",
        audience=PREVIEW_AUDIENCE,
        resource=links.preview_resource("ws", "demo"),
        minutes=5,
    )
    assert read_remote_app_grant(preview) is None
    assert read_remote_app_grant("abi_gk_aaaaaaaaaaaaaaaa_nope") is None
    assert read_remote_app_grant("") is None


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


def _engine_session(user_id: str) -> str:
    from naas_abi.apps.nexus.apps.api.app.services.auth.testing import session_token

    return session_token(credentials.IAM(), user_id)


def test_the_user_and_expiry_come_from_the_engine_session_or_a_link(monkeypatch):
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.apps.app_html_access import (
        mint_app_html_access_token,
    )
    from naas_abi_core.engine.call_context import as_service_account

    iam = credentials.IAM()
    with as_service_account("engine"):
        ada = iam.ensure_user("https://idp.example", "ada")
    request = type("R", (), {})()

    monkeypatch.setattr(http, "extract_abi_api_token", lambda r: _engine_session(ada.id))
    user_id, expires = asyncio.run(http._presented_user(request))
    assert user_id == ada.id and expires is not None
    assert 0 < (expires - datetime.now(UTC)).total_seconds() <= 600  # ten minutes at most
    monkeypatch.setattr(http, "extract_abi_api_token", lambda r: "abi-api-key")
    assert asyncio.run(http._presented_user(request)) == ("", None)
    # A share link (an /app-html/ grant) names its user and ends when it does.
    link, _ = mint_app_html_access_token(user_id="u-8", expires_minutes=30)
    monkeypatch.setattr(http, "extract_abi_api_token", lambda r: link)
    user_id, expires = asyncio.run(http._presented_user(request))
    assert user_id == "u-8" and expires is not None
    assert abs((expires - datetime.now(UTC)).total_seconds() - 1800) < 5
    # A link of another kind is not one.
    grant = _grant(user_id="u-8")
    monkeypatch.setattr(http, "extract_abi_api_token", lambda r: grant)
    assert asyncio.run(http._presented_user(request)) == ("", None)


def test_a_session_its_user_revoked_names_no_user_to_open_an_app_for(monkeypatch):
    import asyncio

    from naas_abi_core.engine.call_context import (
        CallContext,
        as_service_account,
        service_account,
        use_call_context,
        user,
    )

    iam = credentials.IAM()
    with as_service_account("engine"):
        ada = iam.ensure_user("https://idp.example", "ada")
    token = _engine_session(ada.id)
    request = type("R", (), {})()
    monkeypatch.setattr(http, "extract_abi_api_token", lambda r: token)
    assert asyncio.run(http._presented_user(request))[0] == ada.id
    with use_call_context(CallContext(principal=service_account("api"), on_behalf_of=user(ada.id))):
        iam.revoke_tokens(ada.id)
    assert asyncio.run(http._presented_user(request)) == ("", None)


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
