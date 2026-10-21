"""IAM and workspace graph guards at the Maps HTTP boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import (
    acting_as_header,
    knowledge_team,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.service import GraphMapLayer


@pytest.fixture
def boundary(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    config = SimpleNamespace(
        configuration=SimpleNamespace(
            nexus_config=SimpleNamespace(ontology_base_uri="http://ontology.naas.ai/nexus/")
        )
    )
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.primary import fastapi as api
    app = FastAPI()
    provider = Mock(
        return_value={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "one",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"label": "One"},
                }
            ],
            "count": 1,
        }
    )
    api.register_map_layer(
        app,
        GraphMapLayer(
            "example-offices", "Example offices", "Published locations", "urn:locations", provider
        ),
    )
    graph = Mock()
    app.dependency_overrides[api.get_graph_service] = lambda: graph
    acting_as_header(app)
    with knowledge_team():
        yield api, app, provider, graph


def client(app: FastAPI, user: str) -> TestClient:
    return TestClient(app, headers={"x-user": user})


def test_strangers_and_other_workspaces_reach_neither_the_layers_nor_the_feed(boundary):
    api, app, provider, _ = boundary
    with patch.object(api, "workspace_graph_service", AsyncMock()) as scope:
        for user, workspace in (("stranger", "ws-1"), ("member2", "ws-1"), ("member", "ws-2")):
            http = client(app, user)
            assert http.get(f"/api/maps/layers?workspace_id={workspace}").status_code == 403
            feed = http.get(f"/api/maps/layers/example-offices?workspace_id={workspace}")
            assert feed.status_code == 403, (user, workspace)
        scope.assert_not_called()
        provider.assert_not_called()


def test_hides_inaccessible_graph_and_rejects_direct_feed(boundary):
    api, app, provider, _ = boundary
    scoped = Mock(access_scope=GraphAccessScope("ws-1", frozenset({"urn:other"}), frozenset()))
    with patch.object(api, "workspace_graph_service", AsyncMock(return_value=scoped)):
        http = client(app, "viewer")
        assert http.get("/api/maps/layers?workspace_id=ws-1").json() == {"layers": []}
        assert http.get("/api/maps/layers/example-offices?workspace_id=ws-1").status_code == 403
        provider.assert_not_called()


@pytest.mark.parametrize("user", ["viewer", "member", "admin", "owner"])
def test_every_role_reads_an_allowed_layer_from_the_scoped_store_without_cache(boundary, user):
    api, app, provider, graph = boundary
    scoped = Mock(access_scope=GraphAccessScope("ws-1", frozenset({"urn:locations"}), frozenset()))
    with patch.object(api, "workspace_graph_service", AsyncMock(return_value=scoped)) as scope:
        http = client(app, user)
        assert http.get("/api/maps/layers?workspace_id=ws-1").json()["layers"][0]["id"] == (
            "example-offices"
        )
        response = http.get("/api/maps/layers/example-offices?workspace_id=ws-1")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        assert body["type"] == "FeatureCollection"
        assert body["features"][0]["id"] == "one"
        assert http.get("/api/maps/layers/unknown?workspace_id=ws-1").status_code == 404
        # The maps section is checked by the route, not by the graph section's flag.
        scope.assert_awaited_with(graph, user, "ws-1", feature=None)
    provider.assert_called_once_with(scoped._get_triple_store.return_value)


def test_requires_authentication_before_anything(boundary):
    api, app, provider, _ = boundary
    app.dependency_overrides.pop(api.get_current_user_required, None)
    with patch.object(api, "workspace_graph_service", AsyncMock()) as scope:
        with TestClient(app) as http:
            assert http.get("/api/maps/layers?workspace_id=ws-1").status_code == 401
        scope.assert_not_called()
        provider.assert_not_called()


def test_layers_route_is_mounted_once_even_without_graph_layers(boundary):
    api, _, _, _ = boundary
    app = FastAPI()
    catalog = api.install_maps_layers(app)
    assert api.install_maps_layers(app) is catalog
    assert [r.path for r in app.routes].count("/api/maps/layers") == 1
    assert catalog.layers == {}
