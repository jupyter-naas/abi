from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.primary import (
    app_projects__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.object_storage import (
    AppDraftStoreObjectStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.source_control import (
    AppProjectRepositoryGit,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.service import (
    AppProjectsService,
)
from naas_abi.apps.nexus.apps.api.app.services.auth import service as auth_service
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

WS = "ws-1"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    sc = SourceControlService(InMemoryAdapter())
    sc.ensure_repo(owner="abi", name="monorepo")
    service = AppProjectsService(
        repository=AppProjectRepositoryGit(sc, "abi/monorepo"),
        drafts=AppDraftStoreObjectStorage(
            ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
        ),
    )
    app = FastAPI()
    app.include_router(adapter.router, prefix="/api/app-projects")
    app.add_api_route("/app-preview/{token}/{path:path}", adapter.serve_app_preview)
    app.add_api_route("/app-preview/{token}", adapter.redirect_app_preview_root)
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="u-1", email="alice@example.com", name="Alice"
    )
    app.dependency_overrides[adapter.get_app_projects_service] = lambda: service

    async def _members_only(user_id: str, workspace_id: str) -> str:
        if workspace_id != WS:
            raise HTTPException(status_code=403, detail="Not a member")
        return "member"

    monkeypatch.setattr(adapter, "require_workspace_access", _members_only)
    monkeypatch.setattr(adapter.settings, "secret_key", "test-secret")
    monkeypatch.setattr(auth_service.settings, "secret_key", "test-secret")
    return TestClient(app)


def _create(client: TestClient, title: str = "Budget Tracker") -> dict:
    resp = client.post("/api/app-projects/", json={"workspace_id": WS, "title": title})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _preview_path(client: TestClient, slug: str) -> str:
    resp = client.post(f"/api/app-projects/{slug}/preview-token", json={"workspace_id": WS})
    assert resp.status_code == 200, resp.text
    return resp.json()["path"]


def test_create_edit_save_flow(client: TestClient) -> None:
    project = _create(client)
    slug = project["slug"]
    assert project["branch"] == f"apps/{WS}/{slug}"
    assert project["repo_id"] == "abi/monorepo"
    assert {f["path"] for f in project["files"]} >= {"manifest.json", "index.html"}

    resp = client.put(
        f"/api/app-projects/{slug}/file",
        json={"workspace_id": WS, "path": "styles.css", "content": "h1{color:red}"},
    )
    assert resp.status_code == 200, resp.text
    assert client.get(f"/api/app-projects/{slug}", params={"workspace_id": WS}).json()["dirty"]

    resp = client.post(f"/api/app-projects/{slug}/save", json={"workspace_id": WS})
    assert resp.json()["saved"] is True
    resp = client.post(f"/api/app-projects/{slug}/save", json={"workspace_id": WS})
    assert resp.json() == {"saved": False, "commit": None}

    got = client.get(
        f"/api/app-projects/{slug}/file", params={"workspace_id": WS, "path": "styles.css"}
    ).json()
    assert got["content"] == "h1{color:red}"
    history = client.get(f"/api/app-projects/{slug}/history", params={"workspace_id": WS}).json()
    assert len(history) >= 2
    assert [
        p["slug"] for p in client.get("/api/app-projects/", params={"workspace_id": WS}).json()
    ] == [slug]


def test_rules_map_to_http_errors(client: TestClient) -> None:
    slug = _create(client)["slug"]
    resp = client.put(
        f"/api/app-projects/{slug}/file",
        json={"workspace_id": WS, "path": ".env", "content": "SECRET=1"},
    )
    assert resp.status_code == 422
    resp = client.get(
        f"/api/app-projects/{slug}/file", params={"workspace_id": WS, "path": "nope.js"}
    )
    assert resp.status_code == 404
    assert client.get("/api/app-projects/missing", params={"workspace_id": WS}).status_code == 404
    assert (
        client.get(f"/api/app-projects/{slug}", params={"workspace_id": "ws-2"}).status_code == 403
    )


def test_submit_without_configuration_is_a_clear_409(client: TestClient) -> None:
    slug = _create(client)["slug"]
    resp = client.post(f"/api/app-projects/{slug}/submit", json={"workspace_id": WS})
    assert resp.status_code == 409
    assert "not configured" in resp.json()["detail"]


def test_preview_serves_the_draft_in_a_sandboxed_origin(client: TestClient) -> None:
    slug = _create(client)["slug"]
    client.put(
        f"/api/app-projects/{slug}/file",
        json={"workspace_id": WS, "path": "styles.css", "content": "h1{color:red}"},
    )
    path = _preview_path(client, slug)

    page = client.get(path)
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    # main.py's security middleware appends frame-ancestors (core/frame_headers).
    csp = page.headers["content-security-policy"]
    assert csp == adapter.PREVIEW_SANDBOX
    assert "allow-same-origin" not in csp
    assert page.headers["cache-control"] == "no-store"
    assert adapter.PREVIEW_MESSAGE_SOURCE in page.text  # error bridge injected
    assert page.text.index("<head>") < page.text.index(adapter.PREVIEW_MESSAGE_SOURCE)

    css = client.get(f"{path}styles.css")
    assert css.text == "h1{color:red}"  # live draft, not the saved copy
    assert css.headers["content-type"].startswith("text/css")
    assert css.headers["access-control-allow-origin"] == "*"
    assert client.get(f"{path}missing.js").status_code == 404
    assert client.get(f"{path}../../etc/passwd").status_code in (404, 422)


def test_preview_redirects_to_the_trailing_slash(client: TestClient) -> None:
    slug = _create(client)["slug"]
    path = _preview_path(client, slug)
    resp = client.get(path.rstrip("/"), follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == path


def test_preview_token_is_the_only_key(client: TestClient) -> None:
    slug = _create(client)["slug"]
    path = _preview_path(client, slug)
    token = path.split("/")[2]

    assert client.get("/app-preview/forged-token/").status_code == 401
    session, _ = auth_service.create_access_token({"sub": "u-1"})
    assert client.get(f"/app-preview/{session}/").status_code == 401
    # The preview token opens nothing else: it is not a session token.
    assert auth_service.decode_token(token) is None


def test_media_types() -> None:
    assert adapter.media_type_for("app.js") == "text/javascript; charset=utf-8"
    assert adapter.media_type_for("data/catalog.json") == "application/json; charset=utf-8"
    assert adapter.media_type_for("logo.svg") == "image/svg+xml; charset=utf-8"
    assert adapter.media_type_for("photo.webp") == "image/webp"
    assert adapter.media_type_for("Makefile") == "application/octet-stream"


def test_bridge_goes_first_in_head_or_on_top() -> None:
    assert (
        adapter.inject_bridge(b"<html><HEAD lang=x><title>t</title>")
        .decode()
        .startswith("<html><HEAD lang=x><script>")
    )
    assert adapter.inject_bridge(b"<p>no head</p>").decode().startswith("<script>")


def test_own_scripts_report_real_errors() -> None:
    """From the opaque origin an app's scripts are cross-origin: without
    crossorigin the bridge only ever sees "Script error."."""
    html = (
        b'<script src="app.js"></script>'
        b'<script defer src="js/chart.js" type="text/javascript"></script>'
        b'<script src="https://cdn.jsdelivr.net/npm/x.js"></script>'
        b'<script src="//cdn.example.com/y.js"></script>'
        b'<script src="z.js" crossorigin="use-credentials"></script>'
        b"<script>inline()</script>"
    )
    out = adapter.prepare_preview_html(html).decode()
    assert '<script src="app.js" crossorigin="anonymous">' in out
    assert '<script defer src="js/chart.js" type="text/javascript" crossorigin="anonymous">' in out
    assert '<script src="https://cdn.jsdelivr.net/npm/x.js"></script>' in out
    assert '<script src="//cdn.example.com/y.js"></script>' in out
    assert '<script src="z.js" crossorigin="use-credentials"></script>' in out
    assert out.count("crossorigin=") == 3
