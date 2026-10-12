from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import http_routes as http
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


def test_an_upload_above_the_apps_limit_is_refused(monkeypatch):
    small = RemoteApp("acme.research", "console", max_upload_bytes=1000)

    async def never(request):
        raise AssertionError("not forwarded")

    monkeypatch.setattr(
        http, "get_remote_app_directory", lambda: InMemoryRemoteAppDirectory({small: never})
    )
    monkeypatch.setattr(http, "_user_id", lambda request: "")

    response = _client().put("/app-html/remote/acme.research/console/f", content=b"x" * 1001)

    assert response.status_code == 413


def test_a_large_upload_streams_and_a_small_one_is_inline(monkeypatch):
    received = []

    async def handler(request: AppRequest) -> AppResponse:
        if request.body_stream is None:
            received.append(("inline", len(request.body)))
        else:
            size = sum([len(c) async for c in request.body_stream])
            received.append(("stream", size, request.max_body_bytes))
        return AppResponse(200, (), b"ok")

    monkeypatch.setattr(
        http, "get_remote_app_directory", lambda: InMemoryRemoteAppDirectory({CONSOLE: handler})
    )
    monkeypatch.setattr(http, "_user_id", lambda request: "")
    client = _client()

    assert (
        client.put("/app-html/remote/acme.research/console/f", content=b"x" * 1000).status_code
        == 200
    )
    big = b"y" * (3 * 1024 * 1024)
    assert client.put("/app-html/remote/acme.research/console/f", content=big).status_code == 200

    assert received == [("inline", 1000), ("stream", len(big), CONSOLE.upload_limit)]


def test_a_streamed_answer_reaches_the_browser(monkeypatch):
    async def handler(request: AppRequest) -> AppResponse:
        async def events():
            for index in range(3):
                yield f"data: {index}\n\n".encode()

        return AppResponse(200, (("content-type", "text/event-stream"),), body_stream=events())

    monkeypatch.setattr(
        http, "get_remote_app_directory", lambda: InMemoryRemoteAppDirectory({CONSOLE: handler})
    )
    monkeypatch.setattr(http, "_user_id", lambda request: "")

    response = _client().get("/app-html/remote/acme.research/console/events")

    assert response.headers["content-type"] == "text/event-stream"
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
