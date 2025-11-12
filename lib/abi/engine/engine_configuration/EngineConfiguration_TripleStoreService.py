from typing import TYPE_CHECKING, Literal, Union

from abi.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from abi.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageServiceConfiguration,
)
from abi.services.triple_store.TripleStorePorts import ITripleStorePort
from abi.services.triple_store.TripleStoreService import TripleStoreService
from pydantic import BaseModel, model_validator
from typing_extensions import Self

# Only import for type checking, not at runtime
if TYPE_CHECKING:
    pass


class OxigraphAdapterConfiguration(BaseModel):
    oxigraph_url: str = "http://localhost:7878"
    timeout: int = 60


class AWSNeptuneAdapterConfiguration(BaseModel):
    aws_region_name: str
    aws_access_key_id: str
    aws_secret_access_key: str
    db_instance_identifier: str


class AWSNeptuneSSHTunnelAdapterConfiguration(AWSNeptuneAdapterConfiguration):
    bastion_host: str
    bastion_port: int
    bastion_user: str
    bastion_private_key: str


class TripleStoreAdapterFilesystemConfiguration(BaseModel):
    store_path: str
    triples_path: str = "triples"


class TripleStoreAdapterObjectStorageConfiguration(BaseModel):
    object_storage_service: ObjectStorageServiceConfiguration
    triples_prefix: str = "triples"


class TripleStoreAdapterConfiguration(GenericLoader):
    adapter: Literal[
        "oxigraph",
        "aws_neptune_sshtunnel",
        "aws_neptune",
        "fs",
        "object_storage",
        "custom",
    ]
    config: (
        Union[
            OxigraphAdapterConfiguration,
            AWSNeptuneAdapterConfiguration,
            AWSNeptuneSSHTunnelAdapterConfiguration,
            TripleStoreAdapterFilesystemConfiguration,
            TripleStoreAdapterObjectStorageConfiguration,
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_adapter(self) -> Self:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        return self

    def load(self) -> ITripleStorePort:
        if self.adapter != "custom":
            assert self.config is not None, "config is required"

            # Lazy import: only import the adapter that's actually configured
            if self.adapter == "oxigraph":
                from abi.services.triple_store.adaptors.secondary.Oxigraph import (
                    Oxigraph,
                )

                return Oxigraph(**self.config.model_dump())
            elif self.adapter == "aws_neptune":
                from abi.services.triple_store.adaptors.secondary.AWSNeptune import (
                    AWSNeptune,
                )

                return AWSNeptune(**self.config.model_dump())
            elif self.adapter == "aws_neptune_sshtunnel":
                from abi.services.triple_store.adaptors.secondary.AWSNeptune import (
                    AWSNeptuneSSHTunnel,
                )

                return AWSNeptuneSSHTunnel(**self.config.model_dump())
            elif self.adapter == "fs":
                from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
                    TripleStoreService__SecondaryAdaptor__Filesystem,
                )

                return TripleStoreService__SecondaryAdaptor__Filesystem(
                    **self.config.model_dump()
                )
            elif self.adapter == "object_storage":
                from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__ObjectStorage import (
                    TripleStoreService__SecondaryAdaptor__ObjectStorage,
                )

                return TripleStoreService__SecondaryAdaptor__ObjectStorage(
                    **self.config.model_dump()
                )
            else:
                raise ValueError(f"Adapter {self.adapter} not supported")
        else:
            return super().load()


class TripleStoreServiceConfiguration(BaseModel):
    ontology_adapter: TripleStoreAdapterConfiguration

    def load(self) -> TripleStoreService:
        return TripleStoreService(ontology_adaptor=self.ontology_adapter.load())
