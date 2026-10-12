from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import Binding, IGraphQueryStore
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.adapters.secondary.memory import (
    InMemoryMapsFeedLayerStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.service import (
    MapsFeedLayerService,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.primary import (
    maps_layouts__primary_adapter__FastAPI as api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.memory import (
    InMemoryMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)

QUERY = "SELECT ?uri ?label ?lat ?lng WHERE { ?uri <http://ex/name> ?label ; <http://ex/lat> ?lat ; <http://ex/lng> ?lng }"
BODY = {"title": "Offices", "query": QUERY, "graphs": ["http://g/a"]}


class _Store(IGraphQueryStore):
    def select(self, sparql):
        return [
            {
                "uri": Binding("http://ex/p", True),
                "label": Binding("Paris", False),
                "lat": Binding("48.8", False),
                "lng": Binding("2.3", False),
            }
        ]

    def count(self, sparql):
        return 1

    def supports_fulltext(self):
        return False


@pytest.fixture
def client_for(monkeypatch):
    settings = InMemoryMapsSettingsStore()
    service = MapsLayoutService(InMemoryMapsLayoutStore(), settings)
    layers = MapsFeedLayerService(InMemoryMapsFeedLayerStore(), settings, service)
    scoped_calls: list[tuple] = []

    def make(role: str) -> TestClient:
        async def access(user_id, workspace_id):
            return role

        async def admin(user_id, workspace_id):
            if role not in ("owner", "admin"):
                raise HTTPException(status_code=403, detail="admins only")

        async def scoped(user_id, workspace_id, graphs):
            scoped_calls.append((workspace_id, tuple(graphs)))
            return _Store()

        monkeypatch.setattr(api, "require_workspace_access", access)
        monkeypatch.setattr(api, "get_workspace_role", access)
        monkeypatch.setattr(api, "require_workspace_admin", admin)
        monkeypatch.setattr(api, "_scoped_store", scoped)
        app = FastAPI()
        app.include_router(api.router, prefix="/api/maps/layouts")
        app.dependency_overrides[api.get_current_user_required] = lambda: SimpleNamespace(id="u-1")
        app.dependency_overrides[api.get_maps_layout_service] = lambda: service
        app.dependency_overrides[api.get_maps_feed_layer_service] = lambda: layers
        return TestClient(app)

    make.scoped_calls = scoped_calls  # type: ignore[attr-defined]
    return make


def test_admin_creates_layout_and_member_reads_its_feed(client_for) -> None:
    admin = client_for("admin")
    saved = admin.put("/api/maps/layouts/offices?workspace_id=ws-1", json=BODY)
    assert saved.status_code == 200, saved.text

    member = client_for("member")
    listed = member.get("/api/maps/layouts?workspace_id=ws-1").json()
    assert [layout["id"] for layout in listed["layouts"]] == ["offices"]
    assert listed["can_edit"] is False

    feed = member.get("/api/maps/layouts/offices/feed?workspace_id=ws-1")
    assert feed.status_code == 200
    assert feed.json()["features"][0]["properties"]["entityUri"] == "http://ex/p"
    # The query is narrowed to the layout's graphs.
    assert client_for.scoped_calls[-1] == ("ws-1", ("http://g/a",))


def test_members_cannot_edit_hide_or_preview(client_for) -> None:
    member = client_for("member")

    assert member.put("/api/maps/layouts/offices?workspace_id=ws-1", json=BODY).status_code == 403
    assert (
        member.put(
            "/api/maps/layouts/earthquakes/visibility?workspace_id=ws-1", json={"hidden": True}
        ).status_code
        == 403
    )
    assert (
        member.post("/api/maps/layouts/preview", json={**BODY, "workspace_id": "ws-1"}).status_code
        == 403
    )
    assert member.delete("/api/maps/layouts/offices?workspace_id=ws-1").status_code == 403


def test_invalid_layouts_and_builtin_ids_are_refused(client_for) -> None:
    admin = client_for("owner")

    bad = admin.put(
        "/api/maps/layouts/offices?workspace_id=ws-1",
        json={**BODY, "query": "SELECT ?x WHERE { ?x ?p ?o }"},
    )
    assert bad.status_code == 422
    assert any("?lat" in e for e in bad.json()["detail"]["errors"])
    taken = admin.put("/api/maps/layouts/earthquakes?workspace_id=ws-1", json=BODY)
    assert taken.status_code == 422


def test_hiding_builtin_and_custom_layouts(client_for) -> None:
    admin = client_for("admin")
    admin.put("/api/maps/layouts/offices?workspace_id=ws-1", json=BODY)

    admin.put("/api/maps/layouts/earthquakes/visibility?workspace_id=ws-1", json={"hidden": True})
    hidden = admin.put(
        "/api/maps/layouts/offices/visibility?workspace_id=ws-1", json={"hidden": True}
    ).json()

    assert hidden["hidden"] == ["earthquakes", "offices"]
    assert admin.get("/api/maps/layouts?workspace_id=ws-1").json()["hidden"] == [
        "earthquakes",
        "offices",
    ]


def test_preview_reports_errors_or_pins(client_for) -> None:
    admin = client_for("admin")

    invalid = admin.post(
        "/api/maps/layouts/preview", json={**BODY, "workspace_id": "ws-1", "query": "nope"}
    ).json()
    assert invalid["errors"] and invalid["count"] == 0
    ok = admin.post("/api/maps/layouts/preview", json={**BODY, "workspace_id": "ws-1"}).json()
    assert ok["errors"] == [] and ok["count"] == 1 and ok["type"] == "FeatureCollection"
    assert ok["features"][0]["properties"]["label"] == "Paris"


def test_delete_unknown_layout_is_404(client_for) -> None:
    assert client_for("admin").delete("/api/maps/layouts/nope?workspace_id=ws-1").status_code == 404


def test_feed_layer_record_and_colors(client_for) -> None:
    admin = client_for("admin")
    body = {
        "title": "Acme",
        "feed_type": "geojson_url",
        "feed_url": "/api/maps/organization-facilities/acme",
        "category": "organizations-facility",
        "color": "#171c8f",
    }
    assert admin.put("/api/maps/layouts/acme?workspace_id=ws-1", json=body).status_code == 200

    member = client_for("member")
    record = member.get("/api/maps/layouts/acme?workspace_id=ws-1").json()
    assert record["feed_url"] == "/api/maps/organization-facilities/acme"
    assert member.get("/api/maps/layouts/nope?workspace_id=ws-1").status_code == 404
    assert (
        member.put(
            "/api/maps/layouts/earthquakes/color?workspace_id=ws-1", json={"color": "#000000"}
        ).status_code
        == 403
    )

    admin = client_for("admin")
    colored = admin.put(
        "/api/maps/layouts/earthquakes/color?workspace_id=ws-1", json={"color": "#112233"}
    )
    assert colored.json() == {"colors": {"earthquakes": "#112233"}}
    assert admin.get("/api/maps/layouts?workspace_id=ws-1").json()["colors"] == {
        "earthquakes": "#112233"
    }
