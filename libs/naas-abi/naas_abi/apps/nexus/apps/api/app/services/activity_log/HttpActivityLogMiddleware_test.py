import base64
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.activity_log.HttpActivityLogMiddleware import (
    REDACTED,
    HttpActivityLogMiddleware,
)
from naas_abi_core.services.activity_log.ActivityLogFactory import ActivityLogFactory


def _build_app(tmp_path, **mw_kwargs):
    service = ActivityLogFactory.ActivityLogServiceSqlite(data_dir=str(tmp_path))
    app = FastAPI()
    app.state.activity_log_service = service
    app.add_middleware(HttpActivityLogMiddleware, **mw_kwargs)

    @app.get("/hello")
    def _hello():
        return {"ok": True}

    @app.post("/echo")
    async def _echo(request: Request):
        body = await request.json()
        return {"echoed": body}

    @app.post("/api/auth/token")
    async def _token(request: Request):
        await request.body()  # consume
        return {"access_token": "x"}

    @app.post("/upload")
    async def _upload(request: Request):
        await request.body()
        return {"ok": True}

    @app.get("/boom")
    def _boom():
        raise RuntimeError("boom")

    return app, service


@pytest.fixture
def app_with_middleware(tmp_path):
    app, service = _build_app(tmp_path)
    yield app, service
    service.shutdown()


def test_anonymous_request_is_recorded(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    response = client.get("/hello")
    assert response.status_code == 200

    events = service.query("anonymous")
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "http.request"
    assert event.attributes["method"] == "GET"
    assert event.attributes["path"] == "/hello"
    assert event.attributes["status_code"] == 200
    assert event.attributes["duration_ms"] >= 0
    assert event.attributes["has_auth_header"] is False


def test_authenticated_request_is_recorded_under_user_actor(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)

    with patch(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.decode_token",
        return_value={"sub": "user-123"},
    ):
        response = client.get("/hello", headers={"Authorization": "Bearer fake"})

    assert response.status_code == 200
    events = service.query("user:user-123")
    assert len(events) == 1
    assert events[0].attributes["has_auth_header"] is True
    # The token must never appear anywhere in the stored attributes.
    flat = repr(events[0].attributes)
    assert "fake" not in flat


def test_invalid_bearer_token_falls_back_to_anonymous(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)

    with patch(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.decode_token",
        return_value=None,
    ):
        response = client.get("/hello", headers={"Authorization": "Bearer bad"})

    assert response.status_code == 200
    assert len(service.query("anonymous")) == 1


def test_missing_activity_log_service_does_not_break_requests(tmp_path):
    app = FastAPI()
    app.add_middleware(HttpActivityLogMiddleware)

    @app.get("/hello")
    def _hello():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/hello")
    assert response.status_code == 200


def test_failing_request_is_still_recorded(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500

    events = service.query("anonymous")
    assert len(events) == 1
    assert events[0].attributes["status_code"] == 500
    assert events[0].attributes["path"] == "/boom"


def test_correlation_id_is_captured_from_header(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    response = client.get("/hello", headers={"X-Request-Id": "req-xyz"})
    assert response.status_code == 200

    events = service.query("anonymous")
    assert len(events) == 1
    assert events[0].correlation_id == "req-xyz"


def test_json_body_is_captured_and_handler_still_receives_it(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    payload = {"foo": "bar", "n": 42}
    response = client.post("/echo", json=payload)
    assert response.status_code == 200
    assert response.json() == {"echoed": payload}

    events = service.query("anonymous")
    assert len(events) == 1
    body = events[0].attributes["request_body"]
    assert body == payload
    assert events[0].attributes["request_body_size"] > 0


def test_sensitive_keys_are_redacted_at_top_level(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.post(
        "/echo",
        json={"username": "alice", "password": "hunter2", "api_key": "abc"},
    )

    body = service.query("anonymous")[0].attributes["request_body"]
    assert body["username"] == "alice"
    assert body["password"] == REDACTED
    assert body["api_key"] == REDACTED


def test_sensitive_keys_are_redacted_nested_and_in_lists(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.post(
        "/echo",
        json={
            "user": {"name": "alice", "token": "t1"},
            "items": [{"secret": "s1", "other": "ok"}],
        },
    )

    body = service.query("anonymous")[0].attributes["request_body"]
    assert body["user"]["name"] == "alice"
    assert body["user"]["token"] == REDACTED
    assert body["items"][0]["secret"] == REDACTED
    assert body["items"][0]["other"] == "ok"


def test_query_params_are_captured_and_redacted(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    response = client.get("/hello?q=hi&token=secret&page=2")
    assert response.status_code == 200

    qp = service.query("anonymous")[0].attributes["query_params"]
    assert qp["q"] == "hi"
    assert qp["page"] == "2"
    assert qp["token"] == REDACTED


def test_body_truncated_when_over_cap(tmp_path):
    app, service = _build_app(tmp_path, max_body_bytes=128)
    try:
        client = TestClient(app)
        big = "x" * 1024
        client.post("/echo", json={"data": big})

        event = service.query("anonymous")[0]
        assert event.attributes["request_body_truncated"] is True
        assert event.attributes["request_body_size"] > 128
    finally:
        service.shutdown()


def test_auth_path_skips_body_capture(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.post("/api/auth/token", json={"password": "hunter2"})

    body = service.query("anonymous")[0].attributes["request_body"]
    assert isinstance(body, str)
    assert body.startswith("[PATH_SKIPPED")


def test_multipart_body_is_not_captured(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.post(
        "/upload",
        files={"f": ("hello.txt", b"hello world", "text/plain")},
    )

    body = service.query("anonymous")[0].attributes["request_body"]
    assert isinstance(body, str)
    assert body.startswith("[MULTIPART")


def test_binary_body_is_stored_as_base64(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    # Bytes that are not valid UTF-8.
    raw = b"\xff\xfe\x00\x01"
    response = client.post(
        "/upload",
        content=raw,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200

    body = service.query("anonymous")[0].attributes["request_body"]
    assert isinstance(body, dict)
    assert "_b64" in body
    assert base64.b64decode(body["_b64"]) == raw


def test_capture_request_body_can_be_disabled(tmp_path):
    app, service = _build_app(tmp_path, capture_request_body=False)
    try:
        client = TestClient(app)
        client.post("/echo", json={"foo": "bar"})

        body = service.query("anonymous")[0].attributes["request_body"]
        assert isinstance(body, str)
        assert body.startswith("[DISABLED")
    finally:
        service.shutdown()


def test_form_urlencoded_body_is_parsed_and_redacted(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.post(
        "/upload",
        data={"username": "alice", "password": "hunter2"},
    )

    body = service.query("anonymous")[0].attributes["request_body"]
    assert body == {"username": "alice", "password": REDACTED}


def test_authorization_header_value_is_never_stored(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.get("/hello", headers={"Authorization": "Bearer supersecret"})

    flat = repr(service.query("anonymous")[0].attributes)
    assert "supersecret" not in flat
