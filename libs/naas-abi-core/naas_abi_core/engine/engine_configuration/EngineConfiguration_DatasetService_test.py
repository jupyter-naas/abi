from naas_abi_core.engine.engine_configuration.EngineConfiguration_DatasetService import (
    DatasetAdapterConfiguration,
    DatasetAdapterDuckLakeConfiguration,
    DatasetServiceConfiguration,
)
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckLake import (
    DatasetSecondaryAdapterDuckLake,
)
from naas_abi_core.services.dataset.DatasetPort import IDatasetPort
from naas_abi_core.services.dataset.DatasetService import DatasetService


def test_dataset_service_configuration(tmp_path):
    configuration = DatasetServiceConfiguration(
        dataset_adapter=DatasetAdapterConfiguration(
            adapter="ducklake",
            config=DatasetAdapterDuckLakeConfiguration(
                catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
                data_path=str(tmp_path / "datasets"),
            ).model_dump(),
        )
    )
    adapter = configuration.dataset_adapter.load()
    assert isinstance(adapter, IDatasetPort)
    assert isinstance(adapter, DatasetSecondaryAdapterDuckLake)

    service = configuration.load()
    assert isinstance(service, DatasetService)
