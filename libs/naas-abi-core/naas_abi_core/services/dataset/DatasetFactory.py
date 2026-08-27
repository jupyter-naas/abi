from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckDB import (
    DatasetSecondaryAdapterDuckDB,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService


class DatasetFactory:
    @staticmethod
    def DatasetServiceDuckDB(base_path: str) -> DatasetService:
        return DatasetService(DatasetSecondaryAdapterDuckDB(base_path=base_path))
