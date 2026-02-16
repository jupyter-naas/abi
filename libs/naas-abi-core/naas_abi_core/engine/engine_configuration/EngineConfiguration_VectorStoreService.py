from typing import Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.vector_store.IVectorStorePort import IVectorStorePort
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from pydantic import BaseModel, ConfigDict, model_validator


class VectorStoreAdapterQdrantConfiguration(BaseModel):
    """Qdrant vector store adapter configuration.

    vector_store_adapter:
      adapter: "qdrant"
      config:
        host: "{{ secret.QDRANT_HOST }}"
        port: "{{ secret.QDRANT_PORT }}"
        api_key: "{{ secret.QDRANT_API_KEY }}"
        https: "{{ secret.QDRANT_HTTPS }}"
        timeout: "{{ secret.QDRANT_TIMEOUT }}"
    """

    model_config = ConfigDict(extra="forbid")

    host: str = "localhost"
    port: int = 6333
    api_key: str | None = None
    https: bool = False
    timeout: int = 30


class VectorStoreAdapterQdrantInMemoryConfiguration(BaseModel):
    """Qdrant in memory vector store adapter configuration.

    vector_store_adapter:
      adapter: "qdrant_in_memory"
      config: {}
    """

    model_config = ConfigDict(extra="forbid")

    pass


class VectorStoreAdapterConfiguration(GenericLoader):
    adapter: Literal["qdrant", "qdrant_in_memory", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "VectorStoreAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "qdrant":
            pydantic_model_validator(
                VectorStoreAdapterQdrantConfiguration,
                self.config,
                "Invalid configuration for services.vector_store.vector_store_adapter 'qdrant' adapter",
            )

        if self.adapter == "qdrant_in_memory":
            pydantic_model_validator(
                VectorStoreAdapterQdrantInMemoryConfiguration,
                self.config,
                "Invalid configuration for services.vector_store.vector_store_adapter 'qdrant_in_memory' adapter",
            )

        return self

    def load(self) -> IVectorStorePort:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

            # Lazy import: only import when actually loading
            if self.adapter == "qdrant":
                from naas_abi_core.services.vector_store.adapters.QdrantAdapter import (
                    QdrantAdapter,
                )

                return QdrantAdapter(**self.config)
            elif self.adapter == "qdrant_in_memory":
                from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
                    QdrantInMemoryAdapter,
                )

                return QdrantInMemoryAdapter(**self.config)
            else:
                raise ValueError(f"Unknown adapter: {self.adapter}")
        else:
            return super().load()


class VectorStoreServiceConfiguration(BaseModel):
    vector_store_adapter: VectorStoreAdapterConfiguration

    def load(self) -> VectorStoreService:
        return VectorStoreService(adapter=self.vector_store_adapter.load())
