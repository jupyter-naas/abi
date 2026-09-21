"""Authentication and workspace graph guards at the Maps HTTP boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
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
    provider = Mock(return_value={"pins": [{"id": "one"}]})
    api.register_map_layer(
        app,
        GraphMapLayer(
            "example-offices", "Example offices", "Published locations", "urn:locations", provider
        ),
    )
    graph = Mock()
    app.dependency_overrides[api.get_graph_service] = lambda: graph
    return api, app, provider, graph


def test_http_requires_authentication_before_workspace_or_feed(boundary):
    api, app, provider, _ = boundary
    with patch.object(api, "workspace_graph_service", AsyncMock()) as scope:
        with TestClient(app) as client:
            assert client.get("/api/maps/layers?workspace_id=ws").status_code == 401
            assert client.get("/api/maps/layers/example-offices?workspace_id=ws").status_code == 401
        scope.assert_not_called()
        provider.assert_not_called()


def test_http_requires_workspace_membership_before_feed(boundary):
    api, app, provider, graph = boundary
    app.dependency_overrides[api.get_current_user_required] = lambda: SimpleNamespace(id="user")
    with patch.object(
        api, "workspace_graph_service", AsyncMock(side_effect=HTTPException(403, "Forbidden"))
    ) as scope:
        with TestClient(app) as client:
            assert (
                client.get("/api/maps/layers/example-offices?workspace_id=other").status_code == 403
            )
        scope.assert_awaited_once_with(graph, "user", "other")
        provider.assert_not_called()


def test_http_hides_inaccessible_graph_and_rejects_direct_feed(boundary):
    api, app, provider, _ = boundary
    app.dependency_overrides[api.get_current_user_required] = lambda: SimpleNamespace(id="user")
    scoped = Mock(access_scope=GraphAccessScope("ws", frozenset({"urn:other"}), frozenset()))
    with patch.object(api, "workspace_graph_service", AsyncMock(return_value=scoped)):
        with TestClient(app) as client:
            assert client.get("/api/maps/layers?workspace_id=ws").json() == {"layers": []}
            assert client.get("/api/maps/layers/example-offices?workspace_id=ws").status_code == 403
        provider.assert_not_called()


def test_http_allowed_layer_uses_scoped_store_and_no_cache(boundary):
    api, app, provider, _ = boundary
    app.dependency_overrides[api.get_current_user_required] = lambda: SimpleNamespace(id="user")
    scoped = Mock(access_scope=GraphAccessScope("ws", frozenset({"urn:locations"}), frozenset()))
    with patch.object(api, "workspace_graph_service", AsyncMock(return_value=scoped)):
        with TestClient(app) as client:
            assert (
                client.get("/api/maps/layers?workspace_id=ws").json()["layers"][0]["id"]
                == "example-offices"
            )
            response = client.get("/api/maps/layers/example-offices?workspace_id=ws")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["pins"] == [{"id": "one"}]
            assert client.get("/api/maps/layers/unknown?workspace_id=ws").status_code == 404
        provider.assert_called_once_with(scoped._get_triple_store.return_value)
