from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.datasets.datasets__schema import (
    DatasetQueryError,
    DatasetServiceUnavailableError,
    InvalidDatasetIdentifierError,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.service import DatasetsService
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetNotFoundError,
    DatasetSpec,
)


def _service(tmp_path) -> DatasetsService:
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
        [{"person": "maxime", "hours": 2.5}, {"person": "jeremy", "hours": 1.0}],
        namespace="clockify",
    )
    return DatasetsService(warehouse)


def test_list_and_describe(tmp_path) -> None:
    service = _service(tmp_path)
    listed = service.list()
    assert len(listed) == 1
    assert listed[0].namespace == "clockify"
    assert listed[0].name == "hours"
    info = service.describe("hours", namespace="clockify")
    assert [col.name for col in info.columns] == ["person", "hours"]


def test_list_filters_namespace(tmp_path) -> None:
    service = _service(tmp_path)
    assert service.list(namespace="clockify")[0].name == "hours"
    assert service.list(namespace="github") == []


def test_preview_and_query(tmp_path) -> None:
    service = _service(tmp_path)
    preview = service.preview("hours", namespace="clockify", limit=10)
    assert preview.columns == ["person", "hours"]
    assert len(preview.rows) == 2
    result = service.query(
        "SELECT SUM(hours) AS total FROM hours",
        namespace="clockify",
        limit=10,
    )
    assert result.rows[0]["total"] == 3.5
    assert result.truncated is False


def test_query_rejects_write(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(DatasetQueryError):
        service.query("DELETE FROM hours", namespace="clockify")


def test_query_caps_rows(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.query("SELECT * FROM hours", namespace="clockify", limit=1)
    assert len(result.rows) == 1
    assert result.truncated is True
    assert result.limit == 1


def test_unavailable_and_bad_identifier(tmp_path) -> None:
    service = DatasetsService(None)
    with pytest.raises(DatasetServiceUnavailableError):
        service.list()
    empty = DatasetsService(
        DatasetFactory.DatasetServiceDuckLake(
            f"sqlite:{tmp_path / 'empty.sqlite'}", str(tmp_path / "empty")
        )
    )
    with pytest.raises(InvalidDatasetIdentifierError):
        empty.describe("bad-name", namespace="clockify")


def test_describe_missing(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(DatasetNotFoundError):
        service.describe("missing", namespace="clockify")
