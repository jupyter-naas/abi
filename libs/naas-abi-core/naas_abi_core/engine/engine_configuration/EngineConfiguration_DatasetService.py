from typing import Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.dataset.DatasetPort import IDatasetPort
from naas_abi_core.services.dataset.DatasetService import DatasetService
from pydantic import BaseModel, ConfigDict, model_validator


class DatasetAdapterDuckDBConfiguration(BaseModel):
    """DuckDB dataset adapter: Hive-partitioned Parquet on a warehouse path.

    dataset_adapter:
      adapter: "duckdb"
      config:
        base_path: "storage/datastore/datasets"
    """

    model_config = ConfigDict(extra="forbid")

    base_path: str = "storage/datastore/datasets"


class DatasetAdapterConfiguration(GenericLoader):
    adapter: Literal["duckdb", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "DatasetAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "duckdb":
            pydantic_model_validator(
                DatasetAdapterDuckDBConfiguration,
                self.config,
                "Invalid configuration for services.dataset.dataset_adapter 'duckdb' adapter",
            )

        return self

    def load(self) -> IDatasetPort:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )
            if self.adapter == "duckdb":
                from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckDB import (
                    DatasetSecondaryAdapterDuckDB,
                )

                return DatasetSecondaryAdapterDuckDB(**self.config)
            raise ValueError(f"Unknown adapter: {self.adapter}")
        return super().load()


class DatasetServiceConfiguration(BaseModel):
    dataset_adapter: DatasetAdapterConfiguration

    def load(self) -> DatasetService:
        return DatasetService(adapter=self.dataset_adapter.load())
