from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetNotFoundError,
    DatasetSpec,
    IDatasetPort,
    PartitionSpec,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_core.services.dataset.ontologies.classes.ontology_naas_ai.abi.dataset.DatasetCatalogPressure import (
    DatasetCatalogPressure,
)
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.EventService import EventService


@pytest.fixture
def service(tmp_path):
    service = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'catalog.sqlite'}", str(tmp_path / "data")
    )
    for namespace in ("analytics", "other"):
        service.create(
            DatasetSpec(
                name="events",
                namespace=namespace,
                columns=(
                    ColumnSpec(name="id", type="integer"),
                    ColumnSpec(name="region", type="string"),
                ),
                partitions=(PartitionSpec(column="region"),),
                primary_key=("id",),
            )
        )
    return service


def files(service):
    return service.query(
        "SELECT count(*) AS n FROM ducklake_list_files('abi_datasets', 'events', schema => 'analytics')",
        namespace="analytics",
    ).rows[0]["n"]


def test_inline_accumulation_flush_and_history(service):
    snapshots = []
    for batch in range(3):
        snapshots.append(
            service.write(
                "events",
                [
                    {"id": batch * 999 + i, "region": "eu" if i % 2 else "us"}
                    for i in range(999)
                ],
                namespace="analytics",
            )
        )
    assert files(service) == 0
    assert service.inlined_row_count("events", namespace="analytics") == 2997
    service.write("events", [{"id": 1, "region": "eu"}], namespace="other")
    flushed = service.flush("events", namespace="analytics")
    assert sum(row["rows_flushed"] for row in flushed.rows) == 2997
    assert service.inlined_row_count("events", namespace="analytics") == 0
    assert service.inlined_row_count("events", namespace="other") == 1
    assert files(service) == 2
    service.compact("events", namespace="analytics")
    for i, snapshot in enumerate(snapshots):
        assert service.query(
            "SELECT count(*) AS n FROM events",
            namespace="analytics",
            snapshot_id=snapshot.snapshot_id,
        ).rows == [{"n": (i + 1) * 999}]
    assert service.flush("events", namespace="analytics").rows == []


def test_large_batch_bypasses_inlining(service):
    service.write(
        "events",
        [{"id": i, "region": "eu"} for i in range(1001)],
        namespace="analytics",
    )
    assert service.inlined_row_count("events", namespace="analytics") == 0
    assert files(service) == 1


def test_persisted_override_takes_precedence(service):
    service.query(
        "CALL abi_datasets.set_option('data_inlining_row_limit', 0)",
        namespace="analytics",
    )
    service.write("events", [{"id": 1, "region": "eu"}], namespace="analytics")
    assert service.inlined_row_count("events", namespace="analytics") == 0
    assert files(service) == 1


def test_count_across_schema_versions_and_deleted_records(service):
    first = service.write("events", [{"id": 1, "region": "eu"}], namespace="analytics")
    service.query("ALTER TABLE events ADD COLUMN extra VARCHAR", namespace="analytics")
    service.write("events", [{"id": 2, "region": "us"}], namespace="analytics")
    service.query("DELETE FROM events WHERE id = 1", namespace="analytics")
    assert service.inlined_row_count("events", namespace="analytics") == 2
    service.flush("events", namespace="analytics")
    assert service.inlined_row_count("events", namespace="analytics") == 0
    assert service.query("SELECT id FROM events", namespace="analytics").rows == [
        {"id": 2}
    ]
    assert service.query(
        "SELECT id FROM events", namespace="analytics", snapshot_id=first.snapshot_id
    ).rows == [{"id": 1}]


def test_missing_dataset_maintenance(service):
    for operation in (service.flush, service.inlined_row_count):
        with pytest.raises(DatasetNotFoundError):
            operation("missing", namespace="analytics")


def test_stale_inline_catalog_error_retires_reader_without_replaying_sql(service):
    import duckdb

    adapter = service._DatasetService__adapter
    old_connection = adapter._get_read_connection()
    operation = Mock(
        side_effect=duckdb.CatalogException(
            "Failed to read inlined data from DuckLake: Table does not exist"
        )
    )
    with pytest.raises(duckdb.CatalogException):
        adapter._read(operation)
    operation.assert_called_once()
    assert adapter._get_read_connection() is not old_connection
    assert service.query(
        "SELECT count(*) AS n FROM events", namespace="analytics"
    ).rows == [{"n": 0}]


def test_pressure_event_persists_and_roundtrips(tmp_path):
    adapter = Mock(spec=IDatasetPort)
    service = DatasetService(adapter)
    events = EventService(EventSQLiteAdapter(str(tmp_path / "events.sqlite")))
    service.set_services(SimpleNamespace(events_available=lambda: True, events=events))
    adapter.inlined_row_count.return_value = 9
    service.check_catalog_pressure(
        "events", namespace="analytics", threshold_records=10
    )
    assert events.query(DatasetCatalogPressure) == []
    adapter.inlined_row_count.return_value = 10
    assert (
        service.check_catalog_pressure(
            "events", namespace="analytics", threshold_records=10
        )
        == 10
    )
    (event,) = events.query(DatasetCatalogPressure)
    assert event.dataset_name == "events"
    assert event.namespace == "analytics"
    assert event.inlined_records == event.threshold_records == 10
    with pytest.raises(ValueError):
        service.check_catalog_pressure("events", threshold_records=0)


def test_pressure_event_failure_does_not_block_maintenance():
    adapter = Mock(spec=IDatasetPort)
    adapter.inlined_row_count.return_value = 100_000
    service = DatasetService(adapter)
    assert service.check_catalog_pressure("events") == 100_000
    events = Mock()
    events.publish.side_effect = RuntimeError("event store unavailable")
    service.set_services(SimpleNamespace(events_available=lambda: True, events=events))
    assert service.check_catalog_pressure("events") == 100_000
    service.flush("events")
    adapter.flush.assert_called_once_with("events", namespace="default")
