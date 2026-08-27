from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary import (
    datasets__primary_adapter__FastAPI as datasets_api,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.adapters.primary.datasets__primary_adapter__dependencies import (  # noqa: E501
    get_datasets_service,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.service import DatasetsService
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import ColumnSpec, DatasetSpec


def _client(tmp_path, monkeypatch) -> TestClient:
    warehouse = DatasetFactory.DatasetServiceDuckDB(str(tmp_path / "warehouse"))
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
    monkeypatch.setattr(datasets_api, "require_workspace_access", AsyncMock())

    app = FastAPI()
    app.include_router(datasets_api.router, prefix="/datasets")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="admin@example.com", name="Admin"
    )
    app.dependency_overrides[get_datasets_service] = lambda: service
    return TestClient(app)


def test_list_describe_preview_query(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

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


def test_query_rejects_write(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/datasets/clockify/query",
        json={"workspace_id": "ws-1", "sql": "DELETE FROM hours"},
    )
    assert response.status_code == 400


def test_missing_dataset(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get(
        "/datasets/clockify/missing",
        params={"workspace_id": "ws-1"},
    )
    assert response.status_code == 404
