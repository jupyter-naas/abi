from typing import Any

from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckLake import (
    DatasetSecondaryAdapterDuckLake,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService


class DatasetFactory:
    @staticmethod
    def DatasetServiceDuckLake(
        catalog: str, data_path: str, **options: Any
    ) -> DatasetService:
        """``options`` are forwarded to the adapter: retry budget and object-store settings."""
        return DatasetService(
            DatasetSecondaryAdapterDuckLake(
                catalog=catalog, data_path=data_path, **options
            )
        )
