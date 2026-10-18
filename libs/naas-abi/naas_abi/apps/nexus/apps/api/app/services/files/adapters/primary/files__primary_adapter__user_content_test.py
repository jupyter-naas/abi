"""Files a member uploads never run on the API origin, which holds the session cookie.

The real files router (``/raw`` and ``/preview/pdf``) behind the real security
headers middleware, with the authorization and the store stubbed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from naas_abi import ABIModule, NexusConfig
from naas_abi.apps.nexus.apps.api.app.core.config import settings


def _load():
    """The routers read the module's configuration when they are imported."""
    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main
        from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary import (
            files__primary_adapter__FastAPI as files_api,
        )
        from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__dependencies import (  # noqa: E501
            get_files_service,
        )
    return main, files_api, get_files_service


FILES = {
    "x.svg": ("image/svg+xml", b"<svg xmlns='http://www.w3.org/2000/svg'><script>1</script></svg>"),
    "x.html": ("text/html", b"<script>1</script>"),
    "y.js": ("text/javascript", b"1"),
    "x.xml": ("application/xml", b"<a/>"),
    "x.png": ("image/png", b"\x89PNG"),
    "x.pdf": ("application/pdf", b"%PDF"),
    "x.bin": ("application/octet-stream", b"\x00"),
}


class _Files:
    def read_file_raw(self, path: str) -> SimpleNamespace:
        name = path.rsplit("/", 1)[-1]
        media_type, content = FILES[name]
        return SimpleNamespace(content=content, media_type=media_type, filename=name)

    def preview_file_as_pdf(self, path: str) -> SimpleNamespace:
        return SimpleNamespace(content=b"%PDF", filename="x.pdf")


@pytest.fixture
def client(monkeypatch) -> httpx.AsyncClient:
    main, files_api, get_files_service = _load()

    async def authorized(current_user, path, workspace_id, scope, *, files_service):
        return path

    monkeypatch.setattr(files_api, "_authorize_path", authorized)
    app = FastAPI()
    app.include_router(files_api.router, prefix="/api/files")
    app.dependency_overrides[get_files_service] = lambda: _Files()
    app.dependency_overrides[files_api.get_current_user_required] = lambda: SimpleNamespace(id="u")

    @app.get("/api/export/page")
    async def another_route_with_markup() -> HTMLResponse:
        return HTMLResponse("<script>1</script>")

    @app.get("/docs")
    async def docs() -> HTMLResponse:
        return HTMLResponse("<script>swagger</script>")

    app.add_middleware(main.SecurityHeadersMiddleware)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api.test")


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["x.svg", "x.html", "y.js", "x.xml"])
async def test_an_active_upload_is_a_download_in_a_sandbox(client, name):
    response = await client.get(f"/api/files/raw/{name}")
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["content-security-policy"].split(";")[0] == "sandbox"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["x.png", "x.pdf", "x.bin"])
async def test_other_uploads_stay_inline_but_sandboxed(client, name):
    response = await client.get(f"/api/files/raw/{name}")
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["content-security-policy"].split(";")[0] == "sandbox"


@pytest.mark.asyncio
async def test_the_sandbox_stays_in_front_of_the_global_policy_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    response = await client.get("/api/files/raw/y.js")
    policy = response.headers["content-security-policy"]
    # Without it the second upload could be loaded as a script of the first.
    assert policy.startswith("sandbox; ") and "script-src 'self'" in policy

    configured = "default-src 'none'"
    monkeypatch.setattr(settings, "content_security_policy", configured)
    response = await client.get("/api/files/raw/x.svg")
    assert response.headers["content-security-policy"] == f"sandbox; {configured}"


@pytest.mark.asyncio
async def test_the_converted_preview_is_sandboxed_too(client):
    response = await client.get("/api/files/preview/pdf/x.docx")
    assert response.headers["content-security-policy"].split(";")[0] == "sandbox"


@pytest.mark.asyncio
async def test_any_api_route_returning_markup_is_a_sandboxed_download(client):
    response = await client.get("/api/export/page")
    assert response.headers["content-disposition"] == "attachment"
    assert response.headers["content-security-policy"].split(";")[0] == "sandbox"


@pytest.mark.asyncio
async def test_the_development_docs_keep_their_scripts(client):
    response = await client.get("/docs")
    assert "content-disposition" not in response.headers
    assert "sandbox" not in response.headers.get("content-security-policy", "")
