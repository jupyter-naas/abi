from typing import Dict, Literal

from abi.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from abi.services.vector_store.adapters.QdrantAdapter import QdrantAdapter
from abi.services.vector_store.IVectorStorePort import IVectorStorePort
from abi.services.vector_store.VectorStoreService import VectorStoreService
from pydantic import BaseModel, model_validator


class VectorStoreAdapterQdrantConfiguration(BaseModel):
    host: str = "localhost"
    port: int = 6333
    api_key: str
    https: bool = False
    timeout: int = 30


class VectorStoreAdapterConfiguration(GenericLoader):
    adapter: Literal["qdrant", "custom"]
    config: dict | None = None

    __MAPPING: Dict[Literal["qdrant"], type[IVectorStorePort]] = {
        "qdrant": QdrantAdapter,
    }

    @model_validator(mode="after")
    def validate_adapter(self) -> "VectorStoreAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        return self

    def load(self) -> IVectorStorePort:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

            return self.__MAPPING[self.adapter](**self.config)
        else:
            return super().load()


class VectorStoreServiceConfiguration(BaseModel):
    vector_store_adapter: VectorStoreAdapterConfiguration

    def load(self) -> VectorStoreService:
        return VectorStoreService(adapter=self.vector_store_adapter.load())
