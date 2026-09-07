from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import ColumnSpec, DatasetSpec
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
