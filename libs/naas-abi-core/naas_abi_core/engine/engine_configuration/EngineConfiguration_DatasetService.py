from typing import Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.dataset.DatasetPort import IDatasetPort
from naas_abi_core.services.dataset.DatasetService import DatasetService
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DatasetAdapterDuckLakeConfiguration(BaseModel):
    """DuckLake dataset adapter: versioned tables backed by a shared catalog.

    dataset_adapter:
      adapter: "ducklake"
      config:
        catalog: "sqlite:storage/datastore/datasets.sqlite"
        data_path: "storage/datastore/datasets/"
    """

    model_config = ConfigDict(extra="forbid")

    catalog: str = "sqlite:storage/datastore/datasets.sqlite"
    data_path: str = "storage/datastore/datasets/"
    max_retries: int = Field(default=10, ge=0)
    retry_base_delay_seconds: float = Field(default=0.05, ge=0)
    retry_max_delay_seconds: float = Field(default=1.0, ge=0)


class DatasetAdapterConfiguration(GenericLoader):
    adapter: Literal["ducklake", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "DatasetAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "ducklake":
            pydantic_model_validator(
                DatasetAdapterDuckLakeConfiguration,
                self.config,
                "Invalid configuration for services.dataset.dataset_adapter 'ducklake' adapter",
            )

        return self

    def load(self) -> IDatasetPort:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )
            if self.adapter == "ducklake":
                from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckLake import (
                    DatasetSecondaryAdapterDuckLake,
                )

                return DatasetSecondaryAdapterDuckLake(**self.config)
            raise ValueError(f"Unknown adapter: {self.adapter}")
        return super().load()


class DatasetServiceConfiguration(BaseModel):
    dataset_adapter: DatasetAdapterConfiguration

    def load(self) -> DatasetService:
        return DatasetService(adapter=self.dataset_adapter.load())
