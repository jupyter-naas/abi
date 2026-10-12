from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import http
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters.in_memory import (
    InMemoryRemoteAppDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    AppRequest,
    AppResponse,
    RemoteApp,
)
from naas_abi_core.apps.api.abi_api_key_auth import APP_HTML_TOKEN_COOKIE

CONSOLE = RemoteApp("acme.research", "console")


@pytest.fixture
def forwarded(monkeypatch):
    seen: list[AppRequest] = []

    async def answer(request: AppRequest) -> AppResponse:
        seen.append(request)
        return AppResponse(
            200,
            (
                ("content-type", "application/json"),
                ("set-cookie", "theme=dark; Path=/"),
                ("set-cookie", f"{APP_HTML_TOKEN_COOKIE}=stolen; Path=/app-html/"),
                ("transfer-encoding", "chunked"),
            ),
            b'{"ok": true}',
        )

    directory = InMemoryRemoteAppDirectory({CONSOLE: answer})
    monkeypatch.setattr(http, "get_remote_app_directory", lambda: directory)
    monkeypatch.setattr(http, "_user_id", lambda request: "u-42")
    return seen


def _client() -> TestClient:
    app = FastAPI()
    app.add_api_route(
        "/app-html/remote/{module_id}/{app}/{path:path}",
        http.serve_remote_app,
        methods=http.METHODS,
    )
    app.add_api_route(
        "/app-html/remote/{module_id}/{app}", http.redirect_remote_app_root, methods=["GET"]
    )
    return TestClient(app)


def test_requests_reach_the_module_without_the_users_credentials(forwarded):
    client = _client()
    client.cookies.set(APP_HTML_TOKEN_COOKIE, "jwt")
    client.cookies.set("theme", "light")

    response = client.post(
        "/app-html/remote/acme.research/console/api/save?token=jwt&q=1",
        content=b'{"a": 1}',
        headers={"Authorization": "Bearer jwt", "Content-Type": "application/json"},
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
    headers = dict(sent.headers)
    assert "authorization" not in headers
    assert headers["cookie"] == "theme=light"
    assert headers["content-type"] == "application/json"


def test_the_module_cannot_set_the_access_cookie(forwarded):
    response = _client().get("/app-html/remote/acme.research/console/")

    cookies = response.headers.get_list("set-cookie")
    assert cookies == ["theme=dark; Path=/"]
    assert response.headers.get("transfer-encoding") is None
    assert forwarded[0].path == "/"


def test_unknown_apps_are_404(forwarded):
    response = _client().get("/app-html/remote/acme.research/other/")

    assert response.status_code == 404


def test_request_bodies_above_1_mib_are_refused(forwarded):
    response = _client().post(
        "/app-html/remote/acme.research/console/upload", content=b"x" * (1024 * 1024 + 1)
    )

    assert response.status_code == 413
    assert forwarded == []


def test_the_app_root_redirects_to_its_folder(forwarded):
    response = _client().get("/app-html/remote/acme.research/console?x=1", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].endswith("/app-html/remote/acme.research/console/?x=1")


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
