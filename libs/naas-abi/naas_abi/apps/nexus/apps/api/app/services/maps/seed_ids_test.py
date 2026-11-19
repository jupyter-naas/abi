"""Seed ids stay the deployment's: a workspace record never takes one, and a
deployment layer's data is read only through its deployment feed, in the
workspaces the platform policy allows."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import (
    acting_as_header,
    knowledge_team,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.primary import (
    maps_basemaps__primary_adapter__FastAPI as bm_api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.secondary.memory import (
    InMemoryMapsBasemapStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.service import MapsBasemapService
from naas_abi.apps.nexus.apps.api.app.services.maps.cache import MapsCache
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.adapters.primary import (
    maps_feed_layers__primary_adapter__FastAPI as fl_api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.adapters.secondary.memory import (
    InMemoryMapsFeedLayerStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.feed_layers__schema import (
    MapsFeedLayer,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.service import (
    MapsFeedLayerService,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.primary import (
    maps_layouts__primary_adapter__FastAPI as lo_api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.memory import (
    InMemoryMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    FEED_OBJECT_STORAGE,
    MapsLayout,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.objects import (
    MapsObjectMissingError,
    MapsObjectStorePort,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.memory import (
    InMemoryMapsGrantStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KIND_LAYOUT,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.service import (
    MapsAccess,
    MapsActor,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import register_maps_seeds
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.workspace_config import (
    WorkspaceMapsDefaults,
)

SITES = b'{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"name":"SITE-A"},"geometry":{"type":"Point","coordinates":[1,2]}}]}'  # noqa: E501


class Objects(MapsObjectStorePort):
    data = {"restricted/sites.geojson": SITES}

    def read(self, key: str) -> bytes:
        if key not in self.data:
            raise MapsObjectMissingError(key)
        return self.data[key]


@pytest.fixture
def maps():
    settings = InMemoryMapsSettingsStore()
    access = MapsAccess(InMemoryMapsGrantStore())
    layouts = MapsLayoutService(InMemoryMapsLayoutStore(), settings, access)
    layers = MapsFeedLayerService(InMemoryMapsFeedLayerStore(), settings, layouts)
    basemaps = MapsBasemapService(InMemoryMapsBasemapStore(), settings, access)

    app = FastAPI()
    app.include_router(lo_api.router, prefix="/api/maps/layouts")
    app.include_router(fl_api.router, prefix="/api/maps/feed-layers")
    app.include_router(bm_api.router, prefix="/api/maps/basemaps")
    app.dependency_overrides[lo_api.get_maps_layout_service] = lambda: layouts
    app.dependency_overrides[fl_api.get_maps_feed_layer_service] = lambda: layers
    app.dependency_overrides[lo_api.get_maps_feed_layer_service] = lambda: layers
    app.dependency_overrides[lo_api.maps_workspace_defaults] = WorkspaceMapsDefaults
    app.dependency_overrides[fl_api.get_maps_objects] = lambda: Objects()
    app.dependency_overrides[fl_api.get_maps_cache] = lambda: MapsCache(None)
    app.dependency_overrides[bm_api.get_maps_basemap_service] = lambda: basemaps
    acting_as_header(app)

    # A deployment feed and its layer, restricted by the platform to ws-1.
    register_maps_seeds(
        app,
        layouts=[MapsLayout(id="sites-feed", title="Sites", feed_type=FEED_OBJECT_STORAGE)],
        feed_layers=[
            MapsFeedLayer(
                id="sites-layer",
                feed_id="sites-feed",
                title="Sites",
                storage_path="restricted/sites.geojson",
            )
        ],
    )
    asyncio.run(
        access.update(
            KIND_LAYOUT,
            "sites-feed",
            DEPLOYMENT,
            all_workspaces=False,
            workspace_ids={"ws-1"},
            actor=MapsActor("root", True, frozenset({"ws-1", "ws-2"})),
        )
    )
    with knowledge_team():
        yield app, layouts


def _layer_ids(client: TestClient, workspace: str) -> list[str]:
    """The workspace's layers, after its feed list applied the seeds it may use."""
    feeds = client.get(f"/api/maps/layouts?workspace_id={workspace}")
    assert feeds.status_code == 200, feeds.text
    listing = client.get(f"/api/maps/feed-layers?workspace_id={workspace}")
    assert listing.status_code == 200, listing.text
    return [layer["id"] for layer in listing.json()["layers"]]


def test_seed_ids_keep_deployment_data_in_the_workspaces_the_policy_allows(maps):
    app, _ = maps
    allowed = TestClient(app, headers={"x-user": "admin"})
    assert "sites-layer" in _layer_ids(allowed, "ws-1")
    read = allowed.get("/api/maps/feed-layers/sites-layer/data?workspace_id=ws-1")
    assert read.status_code == 200 and "SITE-A" in read.text

    admin = TestClient(app, headers={"x-user": "admin2"})
    viewer = TestClient(app, headers={"x-user": "viewer2"})
    assert admin.get("/api/maps/feed-layers/sites-layer/data?workspace_id=ws-2").status_code == 404

    # A record of the workspace never takes a seed's id: feed, layer or basemap.
    feed = admin.put(
        "/api/maps/layouts/sites-feed?workspace_id=ws-2",
        json={"title": "mine", "feed_type": "object_storage", "group": "x"},
    )
    assert feed.status_code in (400, 422), feed.text
    layer = admin.put(
        "/api/maps/feed-layers/sites-layer?workspace_id=ws-2",
        json={"feed_id": "sites-feed", "title": "mine"},
    )
    assert layer.status_code in (400, 404, 422), layer.text
    basemap = admin.put(
        "/api/maps/basemaps/openstreetmap?workspace_id=ws-2",
        json={
            "title": "mine",
            "category": "custom",
            "renderer": {"kind": "tile", "url": "https://tile.example/{z}/{x}/{y}.png"},
        },
    )
    assert basemap.status_code in (400, 422), basemap.text

    assert "sites-layer" not in _layer_ids(admin, "ws-2")
    for client in (admin, viewer):
        data = client.get("/api/maps/feed-layers/sites-layer/data?workspace_id=ws-2")
        assert data.status_code == 404, data.text
        assert "SITE-A" not in data.text


def test_seed_layers_keep_to_deployment_feeds_even_under_a_stored_record(maps):
    """A workspace record that already holds a seed's id adopts none of its layers."""
    app, layouts = maps
    asyncio.run(
        layouts._store.save(
            "ws-2",
            MapsLayout(id="sites-feed", title="mine", feed_type=FEED_OBJECT_STORAGE),
            user_id="admin2",
        )
    )
    admin = TestClient(app, headers={"x-user": "admin2"})
    assert "sites-layer" not in _layer_ids(admin, "ws-2")
    data = admin.get("/api/maps/feed-layers/sites-layer/data?workspace_id=ws-2")
    assert data.status_code == 404
    assert "SITE-A" not in data.text


def test_seed_copies_keep_their_ids_editable(maps):
    """The workspace's own copy of a seed is still edited under the seed's id."""
    app, _ = maps
    admin = TestClient(app, headers={"x-user": "admin"})
    assert "sites-layer" in _layer_ids(admin, "ws-1")
    renamed = admin.put(
        "/api/maps/layouts/sites-feed?workspace_id=ws-1",
        json={"title": "Sites (renamed)", "feed_type": "object_storage", "group": "x"},
    )
    assert renamed.status_code == 200, renamed.text
    layer = admin.put(
        "/api/maps/feed-layers/sites-layer?workspace_id=ws-1",
        json={"feed_id": "sites-feed", "title": "Sites (renamed)"},
    )
    assert layer.status_code == 200, layer.text
