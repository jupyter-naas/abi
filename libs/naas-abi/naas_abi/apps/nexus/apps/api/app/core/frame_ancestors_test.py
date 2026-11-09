"""Who may frame the module apps: the configured origins, whoever asks.

The real ``SecurityHeadersMiddleware`` in front of stand-ins for the embeddable
routes. A request names a page of its own in ``Origin`` and ``Referer``; the
policy on the response is built from ``frontend_url`` and the CORS origins only.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.testclient import TestClient
from naas_abi import ABIModule, NexusConfig

FRONTEND = "https://nexus.example"
CORS = ["https://nexus.example", "http://localhost:3042", "https://admin.example/"]
SANDBOX = "sandbox allow-scripts allow-forms"
FOREIGN = {"Origin": "https://evil.example", "Referer": "https://other.example/page"}


def _ancestors(response) -> list[str]:
    csp = response.headers["content-security-policy"]
    directive = next(d for d in csp.split(";") if d.strip().startswith("frame-ancestors"))
    return directive.split()[1:]


@pytest.fixture
def client(monkeypatch) -> TestClient:
    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main

    monkeypatch.setattr(main.settings, "enable_security_headers", True)
    monkeypatch.setattr(main.settings, "frontend_url", FRONTEND)

    app = FastAPI()
    app.state.abi_cors_origins = CORS

    @app.get("/app-html/x/apps/x_proxy/")
    def x_proxy() -> Response:
        # What x_proxy answers with: no policy of its own.
        return Response(b"<p>x</p>", media_type="text/html", headers={"ETag": '"v1"'})

    @app.get("/app-html/{path:path}")
    def module_app(path: str) -> HTMLResponse:
        return HTMLResponse("<p>app</p>")

    @app.get("/app-preview/{token}/")
    def preview(token: str) -> HTMLResponse:
        return HTMLResponse("<p>preview</p>", headers={"Content-Security-Policy": SANDBOX})

    @app.get("/app-remote/{path:path}")
    def remote(path: str) -> HTMLResponse:
        return HTMLResponse("<p>remote</p>")

    @app.get("/api/data")
    def data() -> dict[str, str]:
        return {}

    app.add_middleware(main.SecurityHeadersMiddleware)
    return TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/app-html/bob/budget/index.html",
        "/app-html/x/apps/x_proxy/",
        "/app-preview/token/",
        "/app-preview/not-a-real-token/",
        "/app-remote/grant/acme.research/console/index.html",
    ],
)
def test_only_configured_origins_may_frame_an_embeddable_path(client, path):
    asked = client.get(path, headers=FOREIGN)
    quiet = client.get(path)

    assert _ancestors(asked) == [
        "'self'",
        FRONTEND,
        "http://localhost:3042",
        "https://admin.example",
    ]
    assert "evil.example" not in asked.headers["content-security-policy"]
    assert "other.example" not in asked.headers["content-security-policy"]
    # Naming a page changes nothing.
    assert _ancestors(asked) == _ancestors(quiet)
    assert "x-frame-options" not in asked.headers


def test_a_sandboxed_page_naming_no_origin_adds_no_ancestor(client):
    response = client.get("/app-preview/token/", headers={"Origin": "null"})
    assert _ancestors(response)[0] == "'self'"
    assert "null" not in response.headers["content-security-policy"]
    assert " ;" not in response.headers["content-security-policy"]


def test_the_preview_sandbox_stays_first(client):
    response = client.get("/app-preview/token/", headers=FOREIGN)
    assert response.headers["content-security-policy"].startswith(f"{SANDBOX}; frame-ancestors ")


def test_a_module_app_without_its_own_policy_gets_only_the_framing_one(client):
    response = client.get("/app-html/x/apps/x_proxy/", headers=FOREIGN)
    assert response.headers["content-security-policy"].startswith("frame-ancestors ")
    assert response.headers["etag"] == '"v1"'


def test_everything_else_is_still_never_framed(client):
    response = client.get("/api/data", headers=FOREIGN)
    assert response.headers["x-frame-options"] == "DENY"
    assert "evil.example" not in response.headers.get("content-security-policy", "")
