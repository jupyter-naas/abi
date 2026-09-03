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

    ``data_path`` may be an object store URI, in which case the table data lives
    beside everything else the deployment stores rather than on a container disk.
    S3-compatible stores such as MinIO need the endpoint and credentials given
    here: DuckDB has no way to guess them, and a write with none of them set
    fails with HTTP 403 (or, for a batch small enough to be inlined in the
    catalog, silently never reaches the store):

    Include ``http://`` or ``https://`` in the endpoint so TLS is inferred. A
    scheme-less endpoint must set ``s3_use_ssl`` explicitly.

    dataset_adapter:
      adapter: "ducklake"
      config:
        catalog: "postgres:postgresql://user:password@postgres:5432/ducklake"
        data_path: "s3://abi/abi/datastore/datasets/"
        s3_endpoint: "http://minio:9000"
        s3_access_key_id: "{{ secret.MINIO_ROOT_USER }}"
        s3_secret_access_key: "{{ secret.MINIO_ROOT_PASSWORD }}"
    """

    model_config = ConfigDict(extra="forbid")

    catalog: str = "sqlite:storage/datastore/datasets.sqlite"
    data_path: str = "storage/datastore/datasets/"
    max_retries: int = Field(default=10, ge=0)
    retry_base_delay_seconds: float = Field(default=0.05, ge=0)
    retry_max_delay_seconds: float = Field(default=1.0, ge=0)
    s3_endpoint: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = ""
    s3_url_style: str = ""
    s3_use_ssl: bool | None = None

    @model_validator(mode="after")
    def validate_s3_endpoint_transport(self) -> "DatasetAdapterDuckLakeConfiguration":
        endpoint = self.s3_endpoint.strip().lower()
        has_http_scheme = endpoint.startswith(("http://", "https://"))
        if "://" in endpoint and not has_http_scheme:
            raise ValueError("s3_endpoint scheme must be http:// or https://")
        if endpoint and not has_http_scheme and self.s3_use_ssl is None:
            raise ValueError(
                "s3_endpoint must include an http:// or https:// scheme or set "
                "s3_use_ssl explicitly"
            )
        return self


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
