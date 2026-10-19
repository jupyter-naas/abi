from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary import (
    datasets__primary_adapter__FastAPI as datasets_api,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary.datasets__primary_adapter__dependencies import (  # noqa: E501
    get_datasets_service,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.service import DatasetsService
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import ColumnSpec, DatasetSpec


def _client(tmp_path, user: str = "member") -> TestClient:
    warehouse = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "warehouse")
    )
    warehouse.create(
        DatasetSpec(
            name="hours",
            namespace="clockify",
            columns=(
                ColumnSpec(name="person", type="string"),
                ColumnSpec(name="hours", type="double"),
            ),
        )
    )
    warehouse.write(
        "hours",
        [{"person": "maxime", "hours": 2.5}],
        namespace="clockify",
    )
    service = DatasetsService(warehouse)

    app = FastAPI()
    app.include_router(datasets_api.router, prefix="/datasets")
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id=user)
    app.dependency_overrides[get_datasets_service] = lambda: service
    return TestClient(app)


def test_list_describe_preview_query(tmp_path, team) -> None:
    client = _client(tmp_path)

    listed = client.get("/datasets/", params={"workspace_id": "ws-1"})
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == 1
    assert payload["datasets"][0]["name"] == "hours"
    assert payload["datasets"][0]["namespace"] == "clockify"

    described = client.get(
        "/datasets/clockify/hours",
        params={"workspace_id": "ws-1"},
    )
    assert described.status_code == 200
    assert described.json()["columns"][0]["name"] == "person"

    preview = client.get(
        "/datasets/clockify/hours/preview",
        params={"workspace_id": "ws-1", "limit": 10},
    )
    assert preview.status_code == 200
    assert preview.json()["rows"][0]["person"] == "maxime"

    queried = client.post(
        "/datasets/clockify/query",
        json={
            "workspace_id": "ws-1",
            "sql": "SELECT SUM(hours) AS total FROM hours",
            "limit": 10,
        },
    )
    assert queried.status_code == 200
    assert queried.json()["rows"][0]["total"] == 2.5


def test_query_rejects_write(tmp_path, team) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/datasets/clockify/query",
        json={"workspace_id": "ws-1", "sql": "DELETE FROM hours"},
    )
    assert response.status_code == 400


def test_missing_dataset(tmp_path, team) -> None:
    client = _client(tmp_path)
    response = client.get(
        "/datasets/clockify/missing",
        params={"workspace_id": "ws-1"},
    )
    assert response.status_code == 404


QUERY = {"workspace_id": "ws-1", "sql": "SELECT SUM(hours) AS total FROM hours"}


def test_a_viewer_reads_every_dataset_route(tmp_path, team) -> None:
    client = _client(tmp_path, "viewer")
    params = {"workspace_id": "ws-1"}

    assert client.get("/datasets/", params=params).status_code == 200
    assert client.get("/datasets/clockify/hours", params=params).status_code == 200
    assert client.get("/datasets/clockify/hours/preview", params=params).status_code == 200
    assert client.post("/datasets/clockify/query", json=QUERY).json()["rows"][0]["total"] == 2.5


@pytest.mark.parametrize("user", ["stranger"])
def test_a_stranger_reads_nothing(tmp_path, team, user: str) -> None:
    client = _client(tmp_path, user)
    params = {"workspace_id": "ws-1"}

    assert client.get("/datasets/", params=params).status_code == 403
    assert client.get("/datasets/clockify/hours", params=params).status_code == 403
    assert client.get("/datasets/clockify/hours/preview", params=params).status_code == 403
    assert client.post("/datasets/clockify/query", json=QUERY).status_code == 403


def test_the_workspace_of_a_query_is_the_one_asked_of_iam(tmp_path, team) -> None:
    client = _client(tmp_path, "member")

    # The workspace sits in the body: a member of ws-1 asking as ws-2 is refused.
    assert (
        client.post("/datasets/clockify/query", json={**QUERY, "workspace_id": "ws-2"}).status_code
        == 403
    )


def test_a_role_without_the_datasets_feature_is_refused(tmp_path) -> None:
    everything = list(KNOWN_FEATURE_KEYS)
    flags = FeatureFlagsConfig(
        enabled_features=everything,
        role_baseline={
            "owner": everything,
            "admin": everything,
            "member": everything,
            "viewer": ["chat"],
        },
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("viewer", "viewer", scope)
    nexus.grant("member", "member", scope)
    with nexus.installed():
        params = {"workspace_id": "ws-1"}
        denied = _client(tmp_path / "a", "viewer")
        assert denied.get("/datasets/", params=params).status_code == 403
        assert denied.post("/datasets/clockify/query", json=QUERY).status_code == 403
        allowed = _client(tmp_path / "b", "member")
        assert allowed.get("/datasets/", params=params).status_code == 200
