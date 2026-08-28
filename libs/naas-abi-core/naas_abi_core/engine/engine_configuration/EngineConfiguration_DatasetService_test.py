from naas_abi_core.engine.engine_configuration.EngineConfiguration_DatasetService import (
    DatasetAdapterConfiguration,
    DatasetAdapterDuckDBConfiguration,
    DatasetServiceConfiguration,
)
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckDB import (
    DatasetSecondaryAdapterDuckDB,
)
from naas_abi_core.services.dataset.DatasetPort import IDatasetPort
from naas_abi_core.services.dataset.DatasetService import DatasetService


def test_dataset_service_configuration(tmp_path):
    configuration = DatasetServiceConfiguration(
        dataset_adapter=DatasetAdapterConfiguration(
            adapter="duckdb",
            config=DatasetAdapterDuckDBConfiguration(
                base_path=str(tmp_path / "datasets")
            ).model_dump(),
        )
    )
    adapter = configuration.dataset_adapter.load()
    assert isinstance(adapter, IDatasetPort)
    assert isinstance(adapter, DatasetSecondaryAdapterDuckDB)

    service = configuration.load()
    assert isinstance(service, DatasetService)
