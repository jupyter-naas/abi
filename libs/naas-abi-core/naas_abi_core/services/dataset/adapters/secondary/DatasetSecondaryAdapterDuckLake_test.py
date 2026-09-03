import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckLake import (
    DatasetSecondaryAdapterDuckLake,
)
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetSchemaError,
    DatasetSpec,
    PartitionSpec,
)
from naas_abi_core.services.dataset.tests.dataset__secondary_adapter__generic_test import (
    DatasetSecondaryAdapterContract,
)


class TestDatasetSecondaryAdapterDuckLake(DatasetSecondaryAdapterContract):
    @pytest.fixture
    def adapter(self, tmp_path):
        return DatasetSecondaryAdapterDuckLake(
            catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
            data_path=str(tmp_path / "datasets"),
            max_retries=10,
            retry_base_delay_seconds=0.01,
        )

    def test_reserved_column_names_are_quoted(self, adapter):
        spec = DatasetSpec(
            name="time_entries",
            namespace="clockify",
            columns=(
                ColumnSpec(name="id", type="string"),
                ColumnSpec(name="start", type="timestamp"),
                ColumnSpec(name="end", type="timestamp"),
                ColumnSpec(name="duration_hours", type="double"),
            ),
            partitions=(PartitionSpec(column="start", transform="month"),),
            primary_key=("id",),
        )
        adapter.create(spec)
        adapter.write(
            "time_entries",
            [
                {
                    "id": "te-1",
                    "start": "2026-04-15T09:00:00Z",
                    "end": "2026-04-15T12:00:00Z",
                    "duration_hours": 3.0,
                }
            ],
            namespace="clockify",
        )
        total = adapter.query(
            "SELECT SUM(duration_hours) AS hours FROM time_entries",
            namespace="clockify",
        )
        assert total.rows[0]["hours"] == 3.0
        row = adapter.query(
            'SELECT "end" AS ended_at FROM time_entries',
            namespace="clockify",
        )
        assert row.rows[0]["ended_at"] is not None

    def test_upsert_requires_primary_key(self, adapter):
        adapter.create(
            DatasetSpec(
                name="unkeyed",
                columns=(ColumnSpec(name="value", type="string"),),
            )
        )
        with pytest.raises(DatasetSchemaError, match="has no primary key"):
            adapter.write("unkeyed", [{"value": "x"}], mode="upsert")

    def test_delete_preserves_historical_rows(self, adapter):
        adapter.create(
            DatasetSpec(
                name="events",
                columns=(
                    ColumnSpec(name="id", type="integer"),
                    ColumnSpec(name="value", type="string"),
                ),
                primary_key=("id",),
            )
        )
        before_delete = adapter.write("events", [{"id": 1, "value": "keep in history"}])

        adapter.query("DELETE FROM events WHERE id = 1")

        assert adapter.query("SELECT * FROM events").rows == []
        assert adapter.query(
            "SELECT * FROM events", snapshot_id=before_delete.snapshot_id
        ).rows == [{"id": 1, "value": "keep in history"}]

    def test_concurrent_sqlite_writers_preserve_acknowledged_appends(self, adapter):
        adapter.create(
            DatasetSpec(
                name="events",
                columns=(
                    ColumnSpec(name="id", type="integer"),
                    ColumnSpec(name="value", type="string"),
                ),
                primary_key=("id",),
            )
        )

        def append(index: int) -> None:
            adapter.write("events", [{"id": index, "value": f"event-{index}"}])

        with ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(append, range(3)))

        result = adapter.query("SELECT id FROM events ORDER BY id")
        assert [row["id"] for row in result.rows] == list(range(3))

    def test_retriable_attach_conflict_replays_against_fresh_connection(
        self, adapter, monkeypatch
    ):
        import duckdb

        adapter.create(
            DatasetSpec(
                name="events",
                columns=(ColumnSpec(name="id", type="integer"),),
            )
        )
        real_connect = adapter._connect
        attempts = 0

        def flaky_connect(*, snapshot_id=None):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise duckdb.TransactionException("simulated catalog conflict")
            return real_connect(snapshot_id=snapshot_id)

        monkeypatch.setattr(adapter, "_connect", flaky_connect)
        adapter.write("events", [{"id": 1}])

        assert attempts == 3
        assert adapter.query("SELECT * FROM events").rows == [{"id": 1}]


def test_dataset_spec_validates_primary_key_and_partition_columns():
    with pytest.raises(ValueError, match="Primary key columns"):
        DatasetSpec(
            name="events",
            columns=(ColumnSpec(name="id", type="string"),),
            primary_key=("missing",),
        )
    with pytest.raises(ValueError, match="Partition columns"):
        DatasetSpec(
            name="events",
            columns=(ColumnSpec(name="id", type="string"),),
            partitions=(PartitionSpec(column="missing"),),
        )


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("ABI_TEST_DUCKLAKE_POSTGRES") != "1",
    reason="set ABI_TEST_DUCKLAKE_POSTGRES=1 to run the PostgreSQL catalog test",
)
def test_postgres_catalog_concurrent_writers_preserve_acknowledged_appends(tmp_path):
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        "postgres:16-alpine",
        username="ducklake",
        password="ducklake",
        dbname="ducklake",
    ) as postgres:
        catalog = f"postgres:{postgres.get_connection_url(driver=None)}"
        data_path = str(tmp_path / "datasets")
        setup_adapter = DatasetSecondaryAdapterDuckLake(
            catalog=catalog,
            data_path=data_path,
        )
        setup_adapter.create(
            DatasetSpec(
                name="events",
                columns=(
                    ColumnSpec(name="id", type="integer"),
                    ColumnSpec(name="value", type="string"),
                ),
                primary_key=("id",),
            )
        )

        def append(index: int) -> None:
            adapter = DatasetSecondaryAdapterDuckLake(
                catalog=catalog,
                data_path=data_path,
                max_retries=20,
                retry_base_delay_seconds=0.01,
                retry_max_delay_seconds=0.2,
            )
            adapter.write("events", [{"id": index, "value": f"event-{index}"}])

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(append, range(8)))

        result = setup_adapter.query("SELECT id FROM events ORDER BY id")
        assert [row["id"] for row in result.rows] == list(range(8))
