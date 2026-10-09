from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as ws_api,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceRecord
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class _FakeWorkspaces:
    def __init__(self) -> None:
        self.updates: list[str | None] = []
        self.url: str | None = None

    async def get_workspace(self, workspace_id):
        return WorkspaceRecord(
            id=workspace_id,
            name="Demo",
            slug="demo",
            owner_id="user-1",
            background_image_url=self.url,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )

    async def update_workspace(self, workspace_id, updates):
        if updates.background_image_url is not None:
            self.url = updates.background_image_url
        self.updates.append(updates.background_image_url)
        return WorkspaceRecord(
            id=workspace_id,
            name="Demo",
            slug="demo",
            owner_id="user-1",
            background_image_url=self.url,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )


@pytest.fixture
def client_for(tmp_path, monkeypatch):
    files = FilesService(
        storage=ObjectStorageService(
            adapter=ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path))
        )
    )
    workspaces = _FakeWorkspaces()

    def make(role: str) -> tuple[TestClient, _FakeWorkspaces]:
        async def access(user_id, workspace_id):
            return role

        async def no_override(org_id, org_service):
            return None

        monkeypatch.setattr(ws_api, "require_workspace_access", access)
        monkeypatch.setattr(ws_api, "_load_org_role_override", no_override)
        app = FastAPI()
        app.include_router(ws_api.router, prefix="/api/workspaces")
        app.dependency_overrides[ws_api.get_current_user_required] = lambda: SimpleNamespace(
            id="user-1"
        )
        app.dependency_overrides[ws_api.get_files_service] = lambda: files
        app.dependency_overrides[ws_api.get_workspace_service] = lambda: workspaces
        app.dependency_overrides[ws_api.get_organization_service] = lambda: None
        return TestClient(app), workspaces

    return make


def test_members_cannot_stage_but_can_read_the_current_image(client_for) -> None:
    admin, _ = client_for("admin")
    draft = admin.post(
        "/api/workspaces/ws-1/background-image/draft", files={"file": ("a.png", PNG, "image/png")}
    ).json()["draft"]
    committed = admin.post("/api/workspaces/ws-1/background-image", json={"draft": draft})
    assert committed.status_code == 200

    member, _ = client_for("member")
    refused = member.post(
        "/api/workspaces/ws-1/background-image/draft", files={"file": ("a.png", PNG, "image/png")}
    )
    assert refused.status_code == 403
    current = member.get(f"/api/workspaces/ws-1/background-image?v={draft}")
    assert current.status_code == 200
    assert current.content == PNG
    assert "immutable" in current.headers["cache-control"]


def test_stage_preview_commit_updates_workspace(client_for) -> None:
    client, workspaces = client_for("owner")

    staged = client.post(
        "/api/workspaces/ws-1/background-image/draft", files={"file": ("a.png", PNG, "image/png")}
    )
    assert staged.status_code == 200
    draft = staged.json()["draft"]

    preview = client.get(f"/api/workspaces/ws-1/background-image/draft/{draft}")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["cache-control"] == "no-store"

    committed = client.post("/api/workspaces/ws-1/background-image", json={"draft": draft})
    assert committed.status_code == 200
    expected = f"/api/workspaces/ws-1/background-image?v={draft}"
    assert workspaces.updates == [expected]
    # The stored /api/ path passes through to the client unchanged.
    assert committed.json()["background_image_url"] == expected

    # The draft is gone once committed.
    assert client.get(f"/api/workspaces/ws-1/background-image/draft/{draft}").status_code == 404


def test_stage_requires_exactly_one_source_and_a_real_image(client_for) -> None:
    client, _ = client_for("admin")

    assert client.post("/api/workspaces/ws-1/background-image/draft").status_code == 400
    not_image = client.post(
        "/api/workspaces/ws-1/background-image/draft",
        files={"file": ("a.png", b"<html>", "image/png")},
    )
    assert not_image.status_code == 400
    private = client.post(
        "/api/workspaces/ws-1/background-image/draft", data={"url": "http://127.0.0.1/a.png"}
    )
    assert private.status_code == 400


def test_current_restores_the_pointer_when_the_file_is_still_in_home(client_for) -> None:
    client, workspaces = client_for("admin")
    missing = client.get("/api/workspaces/ws-1/background-image/current")
    assert missing.status_code == 404

    draft = client.post(
        "/api/workspaces/ws-1/background-image/draft", files={"file": ("a.png", PNG, "image/png")}
    ).json()["draft"]
    client.post("/api/workspaces/ws-1/background-image", json={"draft": draft})
    # The file stays in .home; the column is what a restart used to clear.
    workspaces.url = None

    current = client.get("/api/workspaces/ws-1/background-image/current")
    assert current.status_code == 200
    expected = f"/api/workspaces/ws-1/background-image?v={draft}"
    assert current.json()["background_image_url"] == expected
    assert workspaces.url == expected


def test_discard_removes_the_draft(client_for) -> None:
    client, _ = client_for("admin")
    draft = client.post(
        "/api/workspaces/ws-1/background-image/draft", files={"file": ("a.png", PNG, "image/png")}
    ).json()["draft"]

    assert client.delete("/api/workspaces/ws-1/background-image/draft").status_code == 200
    assert client.get(f"/api/workspaces/ws-1/background-image/draft/{draft}").status_code == 404


def test_commit_stores_framing_and_rejects_out_of_range_zoom(client_for) -> None:
    client, workspaces = client_for("admin")
    draft = client.post(
        "/api/workspaces/ws-1/background-image/draft", files={"file": ("a.png", PNG, "image/png")}
    ).json()["draft"]

    too_far = client.post("/api/workspaces/ws-1/background-image", json={"draft": draft, "zoom": 9})
    assert too_far.status_code == 422

    ok = client.post(
        "/api/workspaces/ws-1/background-image",
        json={"draft": draft, "x": 30, "y": 70, "zoom": 2},
    )
    assert ok.status_code == 200
    assert (
        workspaces.updates[-1] == f"/api/workspaces/ws-1/background-image?v={draft}&x=30&y=70&z=2"
    )


def test_commit_can_reframe_the_current_image_without_a_draft(client_for) -> None:
    client, workspaces = client_for("admin")
    draft = client.post(
        "/api/workspaces/ws-1/background-image/draft", files={"file": ("a.png", PNG, "image/png")}
    ).json()["draft"]
    client.post("/api/workspaces/ws-1/background-image", json={"draft": draft})

    reframed = client.post(
        "/api/workspaces/ws-1/background-image", json={"current": draft, "zoom": 1.5}
    )
    assert reframed.status_code == 200
    assert (
        workspaces.updates[-1] == f"/api/workspaces/ws-1/background-image?v={draft}&x=50&y=50&z=1.5"
    )
    # The file stays where it is.
    assert client.get(f"/api/workspaces/ws-1/background-image?v={draft}").status_code == 200

    missing = client.post("/api/workspaces/ws-1/background-image", json={"current": "deadbeef.png"})
    assert missing.status_code == 400
    both = client.post(
        "/api/workspaces/ws-1/background-image", json={"draft": draft, "current": draft}
    )
    assert both.status_code == 400
