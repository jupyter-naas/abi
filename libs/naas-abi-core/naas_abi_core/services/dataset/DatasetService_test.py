import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetNotFoundError,
    DatasetSpec,
    PartitionSpec,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService


def test_dataset_service_create_write_query(tmp_path):
    service = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "warehouse")
    )
    assert isinstance(service, DatasetService)
    service.create(
        DatasetSpec(
            name="hours",
            columns=(
                ColumnSpec(name="person", type="string"),
                ColumnSpec(name="hours", type="double"),
            ),
            primary_key=("person",),
        )
    )
    service.write(
        "hours",
        [{"person": "maxime", "hours": 2.5}, {"person": "jeremy", "hours": 1.0}],
    )
    result = service.query("SELECT SUM(hours) AS total FROM hours")
    assert result.rows[0]["total"] == 3.5
    assert service.list_snapshots()


def test_factory_forwards_adapter_options(tmp_path):
    """Object-store and retry settings have to reach the adapter, not be dropped here."""
    service = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}",
        "s3://bucket/warehouse/",
        s3_endpoint="http://minio:9000",
        s3_access_key_id="key",
        s3_secret_access_key="secret",
        max_retries=3,
    )
    adapter = service._DatasetService__adapter
    assert adapter._s3.configured is True
    assert adapter._s3.endpoint == "http://minio:9000"
    assert adapter._max_retries == 3


def test_compaction_merges_partition_files_and_preserves_history(tmp_path):
    service = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "warehouse")
    )
    service.create(
        DatasetSpec(
            name="events",
            namespace="analytics",
            columns=(
                ColumnSpec(name="id", type="integer"),
                ColumnSpec(name="region", type="string"),
            ),
            partitions=(PartitionSpec(column="region"),),
        )
    )
    service.query(
        "CALL abi_datasets.set_option('data_inlining_row_limit', 0)",
        namespace="analytics",
    )
    snapshots = []
    for i in range(3):
        snapshots.append(
            service.write(
                "events",
                [{"id": i, "region": region} for region in ("eu", "us")],
                namespace="analytics",
            )
        )
    files_sql = "SELECT count(*) AS n FROM ducklake_list_files('abi_datasets', 'events', schema => 'analytics')"
    before = service.query(files_sql, namespace="analytics").rows[0]["n"]
    result = service.compact("events", namespace="analytics")
    after = service.query(files_sql, namespace="analytics").rows[0]["n"]
    assert before == 6
    assert after == 2
    assert result.rows
    assert service.query(
        "SELECT count(*) AS n FROM events", namespace="analytics"
    ).rows == [{"n": 6}]
    assert service.query(
        "SELECT count(*) AS n FROM events",
        namespace="analytics",
        snapshot_id=snapshots[0].snapshot_id,
    ).rows == [{"n": 2}]
    service.compact("events", namespace="analytics")
    assert service.query(files_sql, namespace="analytics").rows[0]["n"] == after
    with pytest.raises(DatasetNotFoundError):
        service.compact("missing", namespace="analytics")
