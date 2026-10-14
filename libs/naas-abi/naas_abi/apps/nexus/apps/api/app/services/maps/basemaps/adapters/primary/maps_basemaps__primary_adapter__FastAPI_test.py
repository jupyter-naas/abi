from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.primary import (
    maps_basemaps__primary_adapter__FastAPI as api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.secondary.memory import (
    InMemoryMapsBasemapStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MapsBasemap,
    MapsBasemapPreview,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.service import MapsBasemapService
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import (
    MapsBasemapSeed,
    register_maps_seeds,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.workspace_config import WorkspaceMapsDefaults

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>'
BODY = {"title": "EMEA", "renderer": {"kind": "countries"}}


@pytest.fixture
def client_for(monkeypatch):
    service = MapsBasemapService(InMemoryMapsBasemapStore(), InMemoryMapsSettingsStore())
    app = FastAPI()
    register_maps_seeds(
        app,
        basemaps=[
            MapsBasemapSeed(
                MapsBasemap(
                    id="group-countries",
                    title="Group",
                    category="organization",
                    renderer={"kind": "countries", "palette": {"fill": "#e2e8f0"}},
                ),
                MapsBasemapPreview("image/svg+xml", SVG),
            )
        ],
    )
    app.include_router(api.router, prefix="/api/maps/basemaps")
    app.dependency_overrides[api.get_maps_basemap_service] = lambda: service
    app.dependency_overrides[api.maps_workspace_defaults] = WorkspaceMapsDefaults

    def make(role: str) -> TestClient:
        async def access(user_id, workspace_id):
            return role

        async def admin(user_id, workspace_id):
            if role not in ("owner", "admin"):
                raise HTTPException(status_code=403, detail="admins only")

        monkeypatch.setattr(api, "require_workspace_access", access)
        monkeypatch.setattr(api, "get_workspace_role", access)
        monkeypatch.setattr(api, "require_workspace_admin", admin)
        app.dependency_overrides[api.get_current_user_required] = lambda: SimpleNamespace(id="u-1")
        return TestClient(app)

    return make


def test_member_lists_core_and_deployment_seeds_with_previews(client_for) -> None:
    member = client_for("member")
    listed = member.get("/api/maps/basemaps?workspace_id=ws-1").json()

    ids = [b["id"] for b in listed["basemaps"]]
    assert ids[:4] == ["openstreetmap", "natural-earth", "esri-imagery", "opentopomap"]
    assert ids[4] == "group-countries"
    assert listed["can_edit"] is False

    preview = member.get("/api/maps/basemaps/group-countries/preview?workspace_id=ws-1")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/svg+xml"
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in preview.headers["content-security-policy"]
    assert preview.content == SVG


def test_admin_full_lifecycle(client_for) -> None:
    admin = client_for("admin")
    admin.get("/api/maps/basemaps?workspace_id=ws-1")

    assert admin.put("/api/maps/basemaps/emea?workspace_id=ws-1", json=BODY).status_code == 200
    uploaded = admin.put(
        "/api/maps/basemaps/emea/preview?workspace_id=ws-1",
        content=SVG,
        headers={"Content-Type": "image/svg+xml"},
    )
    assert uploaded.status_code == 200 and uploaded.json()["preview_version"] == 1
    renamed = admin.put(
        "/api/maps/basemaps/emea?workspace_id=ws-1", json={**BODY, "title": "Europe"}
    ).json()
    assert renamed["title"] == "Europe" and renamed["preview_version"] == 1

    hidden = admin.put(
        "/api/maps/basemaps/group-countries/visibility?workspace_id=ws-1", json={"hidden": True}
    ).json()
    assert hidden == {"hidden": ["group-countries"]}
    # Another session reads the same flags from the server.
    assert client_for("member").get("/api/maps/basemaps?workspace_id=ws-1").json()["hidden"] == [
        "group-countries"
    ]

    admin = client_for("admin")
    assert admin.delete("/api/maps/basemaps/group-countries?workspace_id=ws-1").status_code == 409
    assert admin.delete("/api/maps/basemaps/emea?workspace_id=ws-1").status_code == 200
    assert admin.get("/api/maps/basemaps/emea/preview?workspace_id=ws-1").status_code == 404


def test_members_cannot_write(client_for) -> None:
    member = client_for("member")
    assert member.put("/api/maps/basemaps/emea?workspace_id=ws-1", json=BODY).status_code == 403
    assert (
        member.put(
            "/api/maps/basemaps/openstreetmap/visibility?workspace_id=ws-1", json={"hidden": True}
        ).status_code
        == 403
    )
    assert (
        member.put(
            "/api/maps/basemaps/openstreetmap/preview?workspace_id=ws-1",
            content=SVG,
            headers={"Content-Type": "image/svg+xml"},
        ).status_code
        == 403
    )
    assert member.delete("/api/maps/basemaps/emea?workspace_id=ws-1").status_code == 403


def test_bad_previews_and_renderers_are_422(client_for) -> None:
    admin = client_for("owner")
    admin.put("/api/maps/basemaps/emea?workspace_id=ws-1", json=BODY)

    wrong_type = admin.put(
        "/api/maps/basemaps/emea/preview?workspace_id=ws-1",
        content=SVG,
        headers={"Content-Type": "image/png"},
    )
    assert wrong_type.status_code == 422
    too_big = admin.put(
        "/api/maps/basemaps/emea/preview?workspace_id=ws-1",
        content=b"\x89PNG\r\n\x1a\n" + b"\x00" * 600_000,
        headers={"Content-Type": "image/png"},
    )
    assert too_big.status_code == 413
    bad = admin.put(
        "/api/maps/basemaps/emea?workspace_id=ws-1",
        json={"title": "x", "renderer": {"kind": "tile", "url": "javascript:x"}},
    )
    assert bad.status_code == 422
