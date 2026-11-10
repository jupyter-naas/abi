from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import acting_as_header
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.secondary.memory import (
    InMemoryMapsBasemapStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.service import MapsBasemapService
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.memory import (
    InMemoryMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    FEED_GEOJSON_URL,
    MapsLayout,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.primary import (
    maps_permissions__primary_adapter__FastAPI as api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.memory import (
    InMemoryMapsGrantStore,
    InMemoryWorkspaceDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.service import MapsAccess
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import register_maps_seeds
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)

WORKSPACES = {"ws-fm": "Forvis Mazars", "ws-fr": "Forvis Mazars en France", "ws-valeo": "Valeo"}


@pytest.fixture
def setup():
    """Who is what is IAM's: ``root`` administers the platform, ``fr-admin`` is an admin
    of ``ws-fr`` and ``ws-valeo``, ``member`` a member of ``ws-fr``."""
    nexus = NexusIam()
    nexus.org("org-1")
    containers = {workspace: nexus.workspace("org-1", workspace) for workspace in WORKSPACES}
    for workspace in ("ws-fr", "ws-valeo"):
        nexus.grant("fr-admin", "admin", containers[workspace])
    nexus.grant("member", "member", containers["ws-fr"])
    nexus.platform_admin("root")
    with nexus.installed():
        yield from _setup()


def _setup():
    access = MapsAccess(InMemoryMapsGrantStore())
    settings = InMemoryMapsSettingsStore()
    layouts = MapsLayoutService(InMemoryMapsLayoutStore(), settings, access)
    basemaps = MapsBasemapService(InMemoryMapsBasemapStore(), settings, access)
    directory = InMemoryWorkspaceDirectory(WORKSPACES, {"fr-admin": {"ws-fr", "ws-valeo"}})
    app = FastAPI()
    register_maps_seeds(
        app,
        layouts=[
            MapsLayout(
                id=layer_id,
                title=layer_id,
                feed_type=FEED_GEOJSON_URL,
                feed_url=f"/api/maps/organization-facilities/{layer_id}",
            )
            for layer_id in ("forvis-mazars-facilities", "valeo-facilities")
        ],
    )
    app.include_router(api.router, prefix="/api/maps/permissions")
    app.dependency_overrides[api.get_maps_access] = lambda: access
    app.dependency_overrides[api.get_maps_layout_service] = lambda: layouts
    app.dependency_overrides[api.get_maps_basemap_service] = lambda: basemaps
    app.dependency_overrides[api.get_workspace_directory] = lambda: directory

    acting_as_header(app)

    def client(user_id: str) -> TestClient:
        return TestClient(app, headers={"x-user": user_id})

    yield SimpleNamespace(client=client, layouts=layouts)


def _item(body, item_id):
    return next(i for i in body["items"] if i["item_id"] == item_id)


def test_superadmin_restricts_valeo_to_two_workspaces(setup) -> None:
    root = setup.client("root")
    listed = root.get("/api/maps/permissions?workspace_id=ws-fm").json()
    assert [w["id"] for w in listed["workspaces"]] == ["ws-fm", "ws-fr", "ws-valeo"]
    valeo = _item(listed, "valeo-facilities")
    assert valeo["owner"] == "" and valeo["all_workspaces"] and valeo["editable"]
    assert _item(listed, "openstreetmap")["kind"] == "basemap"

    saved = root.put(
        "/api/maps/permissions/layout/valeo-facilities?workspace_id=ws-fm",
        json={"workspace_ids": ["ws-fr", "ws-valeo"]},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["workspace_ids"] == ["ws-fr", "ws-valeo"]

    # Still manageable from a workspace that lost it (to re-enable it there).
    again = root.get("/api/maps/permissions?workspace_id=ws-fm").json()
    assert _item(again, "valeo-facilities")["all_workspaces"] is False
    ids = [layout.id for layout in __import__("asyncio").run(setup.layouts.list("ws-fm")).layouts]
    assert "valeo-facilities" not in ids

    bad = root.put(
        "/api/maps/permissions/layout/valeo-facilities?workspace_id=ws-fm",
        json={"workspace_ids": ["ws-nope"]},
    )
    assert bad.status_code == 422


def test_workspace_admin_cannot_change_deployment_items(setup) -> None:
    admin = setup.client("fr-admin")
    listed = admin.get("/api/maps/permissions?workspace_id=ws-fr").json()
    assert listed["superadmin"] is False
    assert _item(listed, "valeo-facilities")["editable"] is False
    denied = admin.put(
        "/api/maps/permissions/layout/valeo-facilities?workspace_id=ws-fr",
        json={"workspace_ids": ["ws-fr"]},
    )
    assert denied.status_code == 403


def test_workspace_admin_shares_a_custom_layer(setup) -> None:
    import asyncio

    asyncio.run(
        setup.layouts.save(
            "ws-fr",
            MapsLayout(
                id="fr-offices",
                title="FR offices",
                feed_type=FEED_GEOJSON_URL,
                feed_url="/api/maps/organization-facilities/fr",
            ),
            user_id="fr-admin",
        )
    )
    admin = setup.client("fr-admin")
    shared = admin.put(
        "/api/maps/permissions/layout/fr-offices?workspace_id=ws-fr",
        json={"workspace_ids": ["ws-valeo"]},
    )
    assert shared.status_code == 200, shared.text
    everywhere = admin.put(
        "/api/maps/permissions/layout/fr-offices?workspace_id=ws-fr",
        json={"all_workspaces": True},
    )
    assert everywhere.status_code == 403

    seen = admin.get("/api/maps/permissions?workspace_id=ws-valeo").json()
    item = _item(seen, "fr-offices")
    assert item["owner"] == "ws-fr" and item["editable"] is False

    assert setup.client("member").get("/api/maps/permissions?workspace_id=ws-fr").status_code == 403
    admin = setup.client("fr-admin")
    missing = admin.put("/api/maps/permissions/layout/nope?workspace_id=ws-fr", json={})
    assert missing.status_code == 404
