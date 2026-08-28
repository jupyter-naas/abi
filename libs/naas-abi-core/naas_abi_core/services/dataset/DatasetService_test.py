from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import ColumnSpec, DatasetSpec
from naas_abi_core.services.dataset.DatasetService import DatasetService


def test_dataset_service_create_write_query(tmp_path):
    service = DatasetFactory.DatasetServiceDuckDB(str(tmp_path / "warehouse"))
    assert isinstance(service, DatasetService)
    service.create(
        DatasetSpec(
            name="hours",
            columns=(
                ColumnSpec(name="person", type="string"),
                ColumnSpec(name="hours", type="double"),
            ),
        )
    )
    service.write(
        "hours",
        [{"person": "maxime", "hours": 2.5}, {"person": "jeremy", "hours": 1.0}],
    )
    result = service.query("SELECT SUM(hours) AS total FROM hours")
    assert result.rows[0]["total"] == 3.5
