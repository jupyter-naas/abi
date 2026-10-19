"""Tests for ABI API key auth helpers and /app-html middleware."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi_core.apps.api.abi_api_key_auth import (
    AppHtmlAbiKeyMiddleware,
    clear_app_html_token_validators,
    extract_abi_api_token,
    is_abi_api_token_valid,
    is_app_html_request_authorized,
    register_app_html_token_validator,
)
from starlette.requests import Request


@pytest.fixture(autouse=True)
def _reset_validators() -> Iterator[None]:
    clear_app_html_token_validators()
    yield
    clear_app_html_token_validators()


@pytest.fixture()
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = "test-abi-api-key"
    monkeypatch.setenv("ABI_API_KEY", key)
    return key


def test_is_abi_api_token_valid(api_key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    assert is_abi_api_token_valid(api_key) is True
    assert is_abi_api_token_valid("wrong") is False
    assert is_abi_api_token_valid(None) is False
    monkeypatch.delenv("ABI_API_KEY", raising=False)
    assert is_abi_api_token_valid(api_key) is False


def test_extract_abi_api_token_from_header_and_query() -> None:
    header_scope = {
        "type": "http",
        "method": "GET",
        "path": "/app-html/axi/devops/host/",
        "headers": [(b"authorization", b"Bearer header-token")],
        "query_string": b"",
    }
    query_scope = {
        "type": "http",
        "method": "GET",
        "path": "/app-html/axi/devops/host/",
        "headers": [],
        "query_string": b"token=query-token",
    }
    cookie_scope = {
        "type": "http",
        "method": "GET",
        "path": "/app-html/axi/devops/host/",
        "headers": [(b"cookie", b"abi_app_html_token=cookie-token")],
        "query_string": b"",
    }
    assert extract_abi_api_token(Request(header_scope)) == "header-token"
    assert extract_abi_api_token(Request(query_scope)) == "query-token"
    assert extract_abi_api_token(Request(cookie_scope)) == "cookie-token"


def test_app_html_middleware_stamps_cookie_for_scoped_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ABI_API_KEY", raising=False)

    def _accept_jwt(token: str, request: Request) -> bool:
        return token == "jwt-ok" and request.url.path.startswith("/app-html/")

    register_app_html_token_validator(_accept_jwt)

    app = FastAPI()
    app.add_middleware(AppHtmlAbiKeyMiddleware)

    @app.get("/app-html/{path:path}")
    def _html(path: str) -> dict[str, str]:
        return {"path": path}

    client = TestClient(app)
    first = client.get("/app-html/report/counter_uas/map/?token=jwt-ok")
    assert first.status_code == 200
    assert "abi_app_html_token=jwt-ok" in first.headers.get("set-cookie", "")

    # Follow-up asset request uses the cookie (no query token).
    second = client.get("/app-html/report/counter_uas/reports.json")
    assert second.status_code == 200


def test_app_html_middleware_does_not_stamp_cookie_for_api_key(api_key: str) -> None:
    app = FastAPI()
    app.add_middleware(AppHtmlAbiKeyMiddleware)

    @app.get("/app-html/{path:path}")
    def _html(path: str) -> dict[str, str]:
        return {"path": path}

    client = TestClient(app)
    response = client.get(f"/app-html/axi/devops/host/?token={api_key}")
    assert response.status_code == 200
    assert "abi_app_html_token" not in response.headers.get("set-cookie", "")


def test_app_html_middleware_requires_abi_api_key(api_key: str) -> None:
    app = FastAPI()
    app.add_middleware(AppHtmlAbiKeyMiddleware)

    @app.get("/app-html/{path:path}")
    def _html(path: str) -> dict[str, str]:
        return {"path": path}

    @app.get("/health")
    def _health() -> dict[str, str]:
        return {"ok": "1"}

    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/app-html/axi/devops/host/").status_code == 401
    assert (
        client.get(
            "/app-html/axi/devops/host/",
            headers={"Authorization": f"Bearer {api_key}"},
        ).status_code
        == 200
    )
    assert (
        client.get(f"/app-html/axi/devops/host/?token={api_key}").status_code == 200
    )
    # Preflight must not require a token (CORS).
    assert client.options("/app-html/axi/devops/host/").status_code in {200, 405}


def test_app_html_middleware_accepts_registered_jwt_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ABI_API_KEY", raising=False)

    def _accept_jwt(token: str, request: Request) -> bool:
        return token == "jwt-ok" and request.url.path.startswith("/app-html/")

    register_app_html_token_validator(_accept_jwt)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/app-html/axi/devops/host/",
        "headers": [(b"authorization", b"Bearer jwt-ok")],
        "query_string": b"",
    }
    assert is_app_html_request_authorized(Request(scope)) is True

    bad_scope = {
        "type": "http",
        "method": "GET",
        "path": "/app-html/axi/devops/host/",
        "headers": [(b"authorization", b"Bearer wrong")],
        "query_string": b"",
    }
    assert is_app_html_request_authorized(Request(bad_scope)) is False


def test_a_link_is_checked_once_per_request_and_off_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A validator asks IAM, synchronously: the middleware runs it in a thread
    (not on the loop that serves everyone) and once, for the check and for the
    cookie alike."""
    import asyncio
    import threading

    monkeypatch.delenv("ABI_API_KEY", raising=False)
    calls: list[tuple[str, bool]] = []

    def _validator(token: str, request: Request) -> bool:
        try:
            asyncio.get_running_loop()
            on_loop = True
        except RuntimeError:
            on_loop = False
        calls.append((threading.current_thread().name, on_loop))
        return token == "link-ok"

    register_app_html_token_validator(_validator)
    app = FastAPI()
    app.add_middleware(AppHtmlAbiKeyMiddleware)

    @app.get("/app-html/{path:path}")
    def _html(path: str) -> dict[str, str]:
        return {"path": path}

    client = TestClient(app)
    response = client.get("/app-html/axi/devops/host/?token=link-ok")
    assert response.status_code == 200
    assert "abi_app_html_token=link-ok" in response.headers["set-cookie"]
    assert len(calls) == 1
    assert calls[0][1] is False  # no running loop in the thread that validated
    assert client.get("/app-html/axi/?token=nope").status_code == 401
    assert len(calls) == 2
