import pytest
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckDB import (
    DatasetSecondaryAdapterDuckDB,
)
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetSpec,
    PartitionSpec,
)
from naas_abi_core.services.dataset.tests.dataset__secondary_adapter__generic_test import (
    DatasetSecondaryAdapterContract,
)


class TestDatasetSecondaryAdapterDuckDB(DatasetSecondaryAdapterContract):
    @pytest.fixture
    def adapter(self, tmp_path):
        return DatasetSecondaryAdapterDuckDB(base_path=str(tmp_path / "datasets"))

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
