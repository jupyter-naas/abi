import threading
from typing import Any, ClassVar
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.activity_log.HttpActivityLogMiddleware import (
    REDACTED,
    HttpActivityLogMiddleware,
    redact_recorded,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
)
from naas_abi_core.services.activity_log.ActivityLogFactory import ActivityLogFactory
from pydantic import BaseModel, ConfigDict


class Kept(BaseModel):
    """A body model that lets the log keep some of its fields."""

    activity_log_fields: ClassVar[tuple[str, ...]] = (
        "username",
        "password",
        "api_key",
        "client_secret",
        "env_content",
        "user",
        "items",
        "foo",
        "n",
        "data",
        "value",
    )
    model_config = ConfigDict(extra="allow")


def _build_app(tmp_path, **mw_kwargs):
    service = ActivityLogFactory.ActivityLogServiceSqlite(data_dir=str(tmp_path))
    app = FastAPI()
    app.state.activity_log_service = service
    app.add_middleware(HttpActivityLogMiddleware, **mw_kwargs)
    # Outside it, as in main.py: the request's caller is set first.
    app.add_middleware(RequestIdentityMiddleware)

    @app.get("/hello")
    def _hello():
        return {"ok": True}

    @app.post("/echo")
    async def _echo(request: Request):
        body = await request.json()
        return {"echoed": body}

    @app.post("/kept")
    async def _kept(body: Kept):
        return {"echoed": body.model_dump()}

    # Routes that carry credentials: never recorded, even when their model opts in.
    for path in ("/api/secrets", "/api/secrets/s-1", "/api/iam/token", "/idp/login/code"):
        app.add_api_route(path, _kept, methods=["POST"])

    @app.post("/api/auth/token")
    async def _token(request: Request):
        await request.body()  # consume
        return {"access_token": "x"}

    @app.put("/api/admin/system/resources/secret/entry")
    async def _write_secret(request: Request):
        await request.body()
        return {"ok": True}

    @app.post("/upload")
    async def _upload(request: Request):
        await request.body()
        return {"ok": True}

    @app.get("/")
    def _root():
        return {"ok": True}

    @app.get("/health")
    def _health():
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

    # Recorded as Nexus's own account, never under a name the request gives.
    events = service.query("api")
    assert len(events) == 1
    event = events[0]
    assert event.attributes["anonymous"] is True
    assert event.event_type == "http.request"
    assert event.attributes["method"] == "GET"
    assert event.attributes["path"] == "/hello"
    assert event.attributes["status_code"] == 200
    assert event.attributes["duration_ms"] >= 0
    assert event.attributes["has_auth_header"] is False


def test_authenticated_request_is_recorded_under_user_actor(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)

    async def verified(headers, path):
        from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import Credential

        return Credential(kind="session", user_id="user-123"), None

    with patch(
        "naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware.verified_credential",
        verified,
    ):
        response = client.get("/hello", headers={"Authorization": "Bearer fake"})

    assert response.status_code == 200
    events = service.query("user-123")
    assert len(events) == 1
    assert "anonymous" not in events[0].attributes
    assert events[0].attributes["has_auth_header"] is True
    # The token must never appear anywhere in the stored attributes.
    flat = repr(events[0].attributes)
    assert "fake" not in flat


def test_invalid_bearer_token_falls_back_to_anonymous(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)

    async def unverified(headers, path):
        return None, None

    with patch(
        "naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware.verified_credential",
        unverified,
    ):
        response = client.get("/hello", headers={"Authorization": "Bearer bad"})

    assert response.status_code == 200
    assert len(service.query("api")) == 1


def test_health_probes_are_not_recorded(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200

    assert service.query("anonymous") == []


def test_recording_runs_off_the_event_loop_thread():
    recorded_on: list[threading.Thread] = []

    class _Service:
        def record(self, event):
            recorded_on.append(threading.current_thread())

    app = FastAPI()
    app.state.activity_log_service = _Service()
    app.add_middleware(HttpActivityLogMiddleware)
    loop_threads: list[threading.Thread] = []

    @app.get("/hello")
    async def _hello():
        loop_threads.append(threading.current_thread())
        return {"ok": True}

    assert TestClient(app).get("/hello").status_code == 200
    assert len(recorded_on) == 1
    assert recorded_on[0] is not loop_threads[0]


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

    events = service.query("api")
    assert len(events) == 1
    assert events[0].attributes["status_code"] == 500
    assert events[0].attributes["path"] == "/boom"


def test_correlation_id_is_captured_from_header(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    response = client.get("/hello", headers={"X-Request-Id": "req-xyz"})
    assert response.status_code == 200

    events = service.query("api")
    assert len(events) == 1
    assert events[0].correlation_id == "req-xyz"


def test_a_route_keeps_only_the_body_fields_it_names(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    payload = {"foo": "bar", "n": 42, "note": "not kept"}
    response = client.post("/kept", json=payload)
    assert response.status_code == 200
    assert response.json() == {"echoed": payload}

    (event,) = service.query("api")
    assert event.attributes["request_body"] == {"foo": "bar", "n": 42}
    assert event.attributes["request_body_size"] > 0
    # It says what the route kept, and reads back the same.
    assert "foo" in event.attributes["request_body_kept"]
    assert redact_recorded(event.attributes)["request_body"] == {"foo": "bar", "n": 42}


def test_a_route_that_names_no_fields_keeps_no_body(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    payload = {"foo": "bar", "n": 42}
    response = client.post("/echo", json=payload)
    assert response.json() == {"echoed": payload}

    body = service.query("api")[0].attributes["request_body"]
    assert body.startswith("[NOT_RECORDED:")
    assert "bar" not in repr(service.query("api")[0].attributes)


def test_the_request_log_keeps_every_key_naming_a_credential_out(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.post(
        "/kept",
        json={
            "username": "alice",
            "password": "hunter2",
            "api_key": "abc",
            "client_secret": "cs-1",
            "env_content": "OPENAI_API_KEY=sk-1",
            "user": {"name": "alice", "access_token": "t1", "sign_in_code": "123456"},
            "items": [{"secret": "s1", "other": "ok", "privateKey": "k"}],
        },
    )

    body = service.query("api")[0].attributes["request_body"]
    assert body["username"] == "alice"
    assert body["user"]["name"] == "alice"
    assert body["items"][0]["other"] == "ok"
    for kept in ("hunter2", "abc", "cs-1", "sk-1", "t1", "123456", "s1", "'k'"):
        assert kept not in repr(body)


@pytest.mark.parametrize(
    "path", ["/api/secrets", "/api/secrets/s-1", "/api/iam/token", "/idp/login/code"]
)
def test_the_request_log_keeps_credential_routes_bodies_out(app_with_middleware, path):
    app, service = app_with_middleware
    TestClient(app).post(path, json={"value": "the-secret-value", "foo": "bar"})

    (event,) = service.query("api")
    assert event.attributes["request_body"].startswith("[PATH_SKIPPED")
    assert "the-secret-value" not in repr(event.attributes)


def test_the_request_log_keeps_plain_text_and_form_bodies_out(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.post("/upload", data={"username": "alice", "code": "123456"})
    client.post("/upload", content=b"code=654321", headers={"Content-Type": "text/plain"})
    client.post(
        "/upload", content=b"\xff\xfe\x00\x01", headers={"Content-Type": "application/octet-stream"}
    )

    for event in service.query("api"):
        assert event.attributes["request_body"].startswith("[NOT_RECORDED:")
        assert "123456" not in repr(event.attributes)
        assert "654321" not in repr(event.attributes)


def test_an_event_recorded_before_keeps_its_credentials_out_when_read() -> None:
    """What an older version kept, read back as these rules record it."""
    older: dict[str, Any] = {
        "method": "POST",
        "path": "/api/iam/token",
        "request_body": {"client_id": "k-1", "client_secret": "cs-1"},
        "request_body_size": 40,
        "query_params": {"q": "x", "invite_code": "c-1"},
    }
    read = redact_recorded(older)
    assert read["request_body"] == "[PATH_SKIPPED:40]"
    assert read["query_params"] == {"q": "x", "invite_code": REDACTED}
    form = redact_recorded({"path": "/idp-ish", "request_body": "email=a&code=123456"})
    assert form["request_body"] == "[NOT_RECORDED]"
    # A body recorded before the routes named their fields shows as its size, whatever
    # its keys: a form the old decoder kept as a dict, a JSON body of any route.
    for older_body in ({"email": "a@b.c", "code": "123456"}, {"value": "sk-kept-before"}):
        read = redact_recorded({"path": "/x", "request_body": older_body, "request_body_size": 30})
        assert read["request_body"] == "[NOT_RECORDED:30]"
    # One recorded under these rules shows the fields its route kept, and no other.
    kept = redact_recorded(
        {
            "path": "/x",
            "request_body": {"env_content": "A=1", "n": 1, "value": "v"},
            "request_body_kept": ["env_content", "n"],
        }
    )
    assert kept["request_body"] == {"n": 1}
    assert redact_recorded({"path": "/x", "request_body": "[MULTIPART:9]"})["request_body"] == (
        "[MULTIPART:9]"
    )


def test_query_params_are_captured_and_redacted(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    response = client.get("/hello?q=hi&token=secret&page=2&client_token=t2")
    assert response.status_code == 200

    qp = service.query("api")[0].attributes["query_params"]
    assert qp["q"] == "hi"
    assert qp["page"] == "2"
    assert qp["token"] == REDACTED
    assert qp["client_token"] == REDACTED


def test_a_body_over_the_cap_is_recorded_as_its_size(tmp_path):
    app, service = _build_app(tmp_path, max_body_bytes=128)
    try:
        client = TestClient(app)
        big = "x" * 1024
        client.post("/kept", json={"data": big})

        event = service.query("api")[0]
        assert event.attributes["request_body"].startswith("[NOT_RECORDED:")
        assert big not in repr(event.attributes)
    finally:
        service.shutdown()


def test_auth_path_skips_body_capture(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.post("/api/auth/token", json={"password": "hunter2"})

    body = service.query("api")[0].attributes["request_body"]
    assert isinstance(body, str)
    assert body.startswith("[PATH_SKIPPED")


def test_system_app_data_writes_skip_body_capture(app_with_middleware):
    """Super admins write raw service values (secrets, objects) there: never log them."""
    app, service = app_with_middleware
    client = TestClient(app)
    client.put(
        "/api/admin/system/resources/secret/entry?id=OPENAI_API_KEY",
        content=b"sk-not-for-the-log",
        headers={"Content-Type": "text/plain"},
    )

    body = service.query("api")[0].attributes["request_body"]
    assert isinstance(body, str)
    assert body.startswith("[PATH_SKIPPED")
    assert "sk-not-for-the-log" not in repr(service.query("api")[0].attributes)


def test_multipart_body_is_not_captured(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.post(
        "/upload",
        files={"f": ("hello.txt", b"hello world", "text/plain")},
    )

    body = service.query("api")[0].attributes["request_body"]
    assert isinstance(body, str)
    assert body.startswith("[MULTIPART")


def test_capture_request_body_can_be_disabled(tmp_path):
    app, service = _build_app(tmp_path, capture_request_body=False)
    try:
        client = TestClient(app)
        client.post("/echo", json={"foo": "bar"})

        body = service.query("api")[0].attributes["request_body"]
        assert isinstance(body, str)
        assert body.startswith("[DISABLED")
    finally:
        service.shutdown()


def test_authorization_header_value_is_never_stored(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)
    client.get("/hello", headers={"Authorization": "Bearer supersecret"})

    flat = repr(service.query("api")[0].attributes)
    assert "supersecret" not in flat


def test_a_remote_app_grant_never_reaches_the_log(app_with_middleware):
    """The grant in an /app-remote/ path is a bearer credential."""
    app, service = app_with_middleware

    TestClient(app).get("/app-remote/GRANT-SECRET/acme.research/console/index.html")

    (event,) = service.query("api")
    assert event.attributes["path"] == "/app-remote/[grant]/acme.research/console/index.html"
    assert "GRANT-SECRET" not in str(event.attributes)
