from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import acting_as_header, knowledge_team
from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.primary.objects import (
    get_maps_objects,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.adapters.primary import (
    maps_feed_layers__primary_adapter__FastAPI as layers_api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.adapters.secondary.memory import (
    InMemoryMapsFeedLayerStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.service import (
    MapsFeedLayerService,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.primary import (
    maps_layouts__primary_adapter__FastAPI as layouts_api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.memory import (
    InMemoryMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import MapsLayout
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.objects import (
    MapsObjectInvalidError,
    MapsObjectMissingError,
    MapsObjectStorePort,
    layer_features,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.workspace_config import WorkspaceMapsDefaults

DATA = "intelligence/organizations/Acme/maps/acme-facilities.geojson"
LOGO = "intelligence/organizations/Acme/logos/Acme.ico"


def _feature(fid: str, *labels: str) -> dict:
    return {
        "type": "Feature",
        "id": fid,
        "geometry": {"type": "Point", "coordinates": [2.3, 48.8]},
        "properties": {"label": fid, "classLabels": list(labels)},
    }


COLLECTION = {
    "type": "FeatureCollection",
    "features": [_feature("paris", "Office"), _feature("hq", "Office", "Headquarters")],
}


class _Objects(MapsObjectStorePort):
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects
        self.reads: list[str] = []

    def read(self, key: str) -> bytes:
        self.reads.append(key)
        if key not in self.objects:
            raise MapsObjectMissingError(key)
        return self.objects[key]


def test_layer_features_keep_the_layer_feature_types() -> None:
    raw = json.dumps(COLLECTION).encode()
    assert [f["id"] for f in layer_features(raw, ())["features"]] == ["paris", "hq"]
    kept = layer_features(raw, ("Headquarters",))
    assert ([f["id"] for f in kept["features"]], kept["count"]) == (["hq"], 1)
    with pytest.raises(MapsObjectInvalidError):
        layer_features(b'{"type": "Feature"}', ())
    with pytest.raises(MapsObjectInvalidError):
        layer_features(b"{", ())


@pytest.fixture
def client():
    settings = InMemoryMapsSettingsStore()
    feeds = MapsLayoutService(InMemoryMapsLayoutStore(), settings)
    layers = MapsFeedLayerService(InMemoryMapsFeedLayerStore(), settings, feeds)
    objects = _Objects({DATA: json.dumps(COLLECTION).encode(), LOGO: b"\x00\x00\x01\x00icon"})

    feed = MapsLayout(
        id="acme-facilities", title="Acme", feed_type="object_storage", logo_path=LOGO
    )
    seeds_layers = [
        layers_api.MapsFeedLayer(
            id="acme-hq",
            feed_id="acme-facilities",
            title="Headquarters",
            storage_path=DATA,
            class_labels=("Headquarters",),
        ),
        layers_api.MapsFeedLayer(
            id="acme-missing",
            feed_id="acme-facilities",
            title="Missing",
            storage_path="intelligence/organizations/Acme/maps/none.geojson",
        ),
    ]
    asyncio.run(feeds.list("ws-1", seeds=[feed]))
    asyncio.run(layers.list("ws-1", seeds=seeds_layers))

    app = FastAPI()
    app.include_router(layers_api.router, prefix="/api/maps/feed-layers")
    app.include_router(layouts_api.router, prefix="/api/maps/layouts")
    acting_as_header(app)
    app.dependency_overrides[layouts_api.get_maps_layout_service] = lambda: feeds
    app.dependency_overrides[layouts_api.maps_workspace_defaults] = WorkspaceMapsDefaults
    app.dependency_overrides[layers_api.get_maps_feed_layer_service] = lambda: layers
    app.dependency_overrides[get_maps_objects] = lambda: objects
    # ``member`` is a member of ``ws-1`` only.
    test_client = TestClient(app, headers={"x-user": "member"})
    test_client.objects = objects  # type: ignore[attr-defined]
    with knowledge_team():
        yield test_client


def test_layer_data_is_read_from_the_layer_record(client) -> None:
    ok = client.get("/api/maps/feed-layers/acme-hq/data", params={"workspace_id": "ws-1"})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert [f["id"] for f in body["features"]] == ["hq"]
    assert (body["layer_title"], body["source"]) == ("Headquarters", "Acme")
    assert ok.headers["cache-control"] == "private, no-cache"
    assert client.objects.reads == [DATA]

    # Same object, same layer: the browser revalidates with the ETag.
    again = client.get(
        "/api/maps/feed-layers/acme-hq/data",
        params={"workspace_id": "ws-1"},
        headers={"If-None-Match": ok.headers["etag"]},
    )
    assert again.status_code == 304


def test_layer_data_refusals(client) -> None:
    get = lambda layer, ws="ws-1": client.get(  # noqa: E731
        f"/api/maps/feed-layers/{layer}/data", params={"workspace_id": ws}
    )
    assert get("acme-hq", "ws-2").status_code == 403
    assert get("unknown").status_code == 404
    missing = get("acme-missing")
    assert missing.status_code == 503
    assert "not published" in missing.json()["detail"]


def test_feed_logo_is_read_from_the_feed_record(client) -> None:
    ok = client.get("/api/maps/layouts/acme-facilities/logo", params={"workspace_id": "ws-1"})
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/x-icon"
    assert ok.content == b"\x00\x00\x01\x00icon"
    assert (
        client.get(
            "/api/maps/layouts/acme-facilities/logo", params={"workspace_id": "ws-2"}
        ).status_code
        == 403
    )
    assert (
        client.get("/api/maps/layouts/unknown/logo", params={"workspace_id": "ws-1"}).status_code
        == 404
    )


def test_oversized_logo_is_refused(client) -> None:
    client.objects.objects[LOGO] = b"x" * 600_000
    assert (
        client.get(
            "/api/maps/layouts/acme-facilities/logo", params={"workspace_id": "ws-1"}
        ).status_code
        == 502
    )


def test_all_features_of_the_layer_object_for_the_feature_type_picker(client) -> None:
    every = client.get(
        "/api/maps/feed-layers/acme-hq/data", params={"workspace_id": "ws-1", "all": "true"}
    )
    assert [f["id"] for f in every.json()["features"]] == ["paris", "hq"]


def test_layer_features_keep_the_collection_metadata() -> None:
    raw = json.dumps(
        {**COLLECTION, "mapRegions": {"regions": [1]}, "observation_date": "2026-10-12"}
    )
    out = layer_features(raw.encode(), ("Headquarters",))
    assert (out["mapRegions"], out["observation_date"], out["count"]) == (
        {"regions": [1]},
        "2026-10-12",
        1,
    )
