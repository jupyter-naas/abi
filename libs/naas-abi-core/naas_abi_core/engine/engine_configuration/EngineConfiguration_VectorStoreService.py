from typing import Literal, Self

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

    storage_path: str = ":memory:"
    timeout: int = 300


class VectorStoreAdapterSqliteVecConfiguration(BaseModel):
    """SQLite + sqlite-vec vector store adapter configuration.

    File-backed, multi-process safe via SQLite WAL. Used as the dev default
    so api and dagster can share the store without a server.

    vector_store_adapter:
      adapter: "sqlite_vec"
      config:
        persistence_path: "storage/vectorstore/vectors.sqlite3"
        journal_mode: "WAL"
        busy_timeout_ms: 5000
    """

    model_config = ConfigDict(extra="forbid")

    persistence_path: str
    journal_mode: str = "WAL"
    busy_timeout_ms: int = 5000


class VectorStoreAdapterNATSConfiguration(BaseModel):
    """Vector store adapter NATS RPC client configuration.

    Talks to a remote ``VectorStorePrimaryAdapterNATS`` over NATS
    request/reply -- see docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md
    (Stage 1) and naas_abi_core/proto/vector_store/v1/vector_store.proto.

    vector_store_adapter:
      adapter: "nats_rpc"
      config:
        nats_url: "nats://127.0.0.1:4222"
        jwt_secret: "{{ secret.NATS_SERVICE_JWT_SECRET }}"
        service_identity: "api"
    """

    model_config = ConfigDict(extra="forbid")

    nats_url: str = "nats://127.0.0.1:4222"
    jwt_secret: str
    service_identity: str = "api"


class VectorStoreAdapterConfiguration(GenericLoader):
    adapter: Literal["qdrant", "qdrant_in_memory", "sqlite_vec", "nats_rpc", "custom"]
    # Deliberately a loose dict, not a typed Union of the adapter config
    # classes above (unlike object_storage's equivalent field): qdrant/
    # qdrant_in_memory/sqlite_vec all have every field defaulted, so an
    # untagged Union can't reliably tell them apart from a minimal/empty
    # config dict -- pydantic would happily bind `{}` to whichever member
    # comes first in the Union regardless of what `adapter:` actually says.
    # The per-adapter `pydantic_model_validator` calls in `validate_adapter`
    # below do the real type-checking, branching on `self.adapter` first
    # (which is unambiguous), so this field only needs to accept "a dict".
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> Self:
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

        if self.adapter == "sqlite_vec":
            pydantic_model_validator(
                VectorStoreAdapterSqliteVecConfiguration,
                self.config,
                "Invalid configuration for services.vector_store.vector_store_adapter 'sqlite_vec' adapter",
            )

        if self.adapter == "nats_rpc":
            pydantic_model_validator(
                VectorStoreAdapterNATSConfiguration,
                self.config,
                "Invalid configuration for services.vector_store.vector_store_adapter 'nats_rpc' adapter",
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
            elif self.adapter == "sqlite_vec":
                from naas_abi_core.services.vector_store.adapters.SqliteVecAdapter import (
                    SqliteVecAdapter,
                )

                return SqliteVecAdapter(**self.config)
            elif self.adapter == "nats_rpc":
                from naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient import (
                    VectorStoreSecondaryAdapterNATSClient,
                )

                return VectorStoreSecondaryAdapterNATSClient(**self.config)
            else:
                raise ValueError(f"Unknown adapter: {self.adapter}")
        else:
            return super().load()


class VectorStoreServiceConfiguration(BaseModel):
    vector_store_adapter: VectorStoreAdapterConfiguration

    def load(self) -> VectorStoreService:
        return VectorStoreService(adapter=self.vector_store_adapter.load())
