from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.activity_log.HttpActivityLogMiddleware import (
    HttpActivityLogMiddleware,
)
from naas_abi_core.services.activity_log.ActivityLogFactory import ActivityLogFactory


@pytest.fixture
def app_with_middleware(tmp_path):
    service = ActivityLogFactory.ActivityLogServiceSqlite(data_dir=str(tmp_path))
    app = FastAPI()
    app.state.activity_log_service = service
    app.add_middleware(HttpActivityLogMiddleware)

    @app.get("/hello")
    def _hello():
        return {"ok": True}

    @app.get("/boom")
    def _boom():
        raise RuntimeError("boom")

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


def test_authenticated_request_is_recorded_under_user_actor(app_with_middleware):
    app, service = app_with_middleware
    client = TestClient(app)

    with patch(
        "naas_abi.apps.nexus.apps.api.app.services.activity_log."
        "HttpActivityLogMiddleware.decode_token"
    ) if False else patch(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.decode_token",
        return_value={"sub": "user-123"},
    ):
        response = client.get("/hello", headers={"Authorization": "Bearer fake"})

    assert response.status_code == 200
    events = service.query("user:user-123")
    assert len(events) == 1
    assert events[0].attributes["path"] == "/hello"


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
    # No app.state.activity_log_service set on purpose.
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
