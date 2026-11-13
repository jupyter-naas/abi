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
    routed_path,
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


def _app_html_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AppHtmlAbiKeyMiddleware)

    @app.get("/app-html/{path:path}")
    def _html(path: str) -> dict[str, str]:
        return {"path": path}

    return app


def test_app_html_access_keeps_the_routed_path_whatever_the_host(api_key: str) -> None:
    """The check covers the path the router serves, whatever ``Host`` says."""
    client = TestClient(_app_html_app(), base_url="http://abi.local")
    for host in ("abi.local/elsewhere?q=", "abi.local/health#", "abi.local"):
        response = client.get("/app-html/x/apps/x_proxy/index.html", headers={"host": host})
        assert response.status_code in {400, 401}, host
        assert "path" not in response.text


def _url_showing(url: object) -> property:
    def shown(self: Request) -> object:
        return url

    return property(shown)


def test_app_html_access_keeps_the_routed_path_when_the_url_differs(
    api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``request.url`` that names another path changes nothing: the middleware
    and the validators decide on the path the router serves."""
    from starlette.datastructures import URL

    seen: list[str] = []

    def _validator(token: str, request: Request) -> bool:
        seen.append(routed_path(request))
        return token == "link-for-a" and routed_path(request).startswith("/app-html/a/")

    register_app_html_token_validator(_validator)
    client = TestClient(_app_html_app())
    for shown in ("http://abi.local/health", "http://abi.local/app-html/a/x"):
        monkeypatch.setattr(Request, "url", _url_showing(URL(shown)))
        assert client.get("/app-html/b/secret.html").status_code == 401
        assert client.get("/app-html/b/secret.html?token=link-for-a").status_code == 401
        assert client.get("/app-html/a/page.html?token=link-for-a").status_code == 200
    assert set(seen) == {"/app-html/b/secret.html", "/app-html/a/page.html"}


@pytest.fixture()
def retired_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """A key made retired for the test: only its hash is listed."""
    import hashlib

    from naas_abi_core.apps.api import abi_api_key_auth

    value = "a-key-that-was-published-once"
    digest = hashlib.sha256(value.encode()).hexdigest()
    monkeypatch.setattr(
        abi_api_key_auth,
        "RETIRED_ABI_API_KEY_SHA256",
        abi_api_key_auth.RETIRED_ABI_API_KEY_SHA256 | {digest},
    )
    return value


def test_retired_api_keys_are_kept_as_hashes_only() -> None:
    from naas_abi_core.apps.api.abi_api_key_auth import RETIRED_ABI_API_KEY_SHA256

    assert RETIRED_ABI_API_KEY_SHA256
    for digest in RETIRED_ABI_API_KEY_SHA256:
        assert len(digest) == 64 and set(digest) <= set("0123456789abcdef")


def test_api_key_keeps_retired_values_refused(
    retired_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from naas_abi_core.apps.api.abi_api_key_auth import (
        RetiredAbiApiKeyError,
        is_retired_abi_api_key,
        refuse_retired_abi_api_key,
    )

    assert is_retired_abi_api_key(retired_key)
    assert is_retired_abi_api_key(f" {retired_key}\n")
    assert not is_retired_abi_api_key("a-fresh-random-key")
    assert not is_retired_abi_api_key(None)

    monkeypatch.setenv("ABI_API_KEY", retired_key)
    with pytest.raises(RetiredAbiApiKeyError) as raised:
        refuse_retired_abi_api_key()
    assert retired_key not in str(raised.value)
    # Even if something serves anyway, the value opens nothing.
    assert is_abi_api_token_valid(retired_key) is False
    client = TestClient(_app_html_app())
    assert client.get(f"/app-html/a/?token={retired_key}").status_code == 401

    monkeypatch.setenv("ABI_API_KEY", "a-fresh-random-key")
    refuse_retired_abi_api_key()
    assert is_abi_api_token_valid("a-fresh-random-key") is True


def test_api_keeps_from_starting_with_a_retired_key(
    retired_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The API stops before the engine loads when its key is retired."""
    from naas_abi_core.apps.api import api as api_module
    from naas_abi_core.apps.api.abi_api_key_auth import RetiredAbiApiKeyError

    loaded: list[bool] = []
    monkeypatch.setattr(api_module, "_load_runtime_routes", lambda: loaded.append(True))
    monkeypatch.setenv("ABI_API_KEY", retired_key)
    with pytest.raises(RetiredAbiApiKeyError):
        api_module.get_app()
    assert loaded == []

    monkeypatch.setenv("ABI_API_KEY", "a-fresh-random-key")
    assert api_module.get_app() is api_module.app
    assert loaded == [True]
