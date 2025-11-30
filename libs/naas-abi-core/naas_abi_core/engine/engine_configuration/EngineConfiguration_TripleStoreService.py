from typing import TYPE_CHECKING, Literal, Union

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStorePort
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
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
            dict,
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_adapter(self) -> Self:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "fs":
            pydantic_model_validator(
                TripleStoreAdapterFilesystemConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'fs' adapter",
            )
        if self.adapter == "object_storage":
            pydantic_model_validator(
                TripleStoreAdapterObjectStorageConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'object_storage' adapter",
            )
        if self.adapter == "oxigraph":
            pydantic_model_validator(
                OxigraphAdapterConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'oxigraph' adapter",
            )
        if self.adapter == "aws_neptune":
            pydantic_model_validator(
                AWSNeptuneAdapterConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'aws_neptune' adapter",
            )
        if self.adapter == "aws_neptune_sshtunnel":
            pydantic_model_validator(
                AWSNeptuneSSHTunnelAdapterConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'aws_neptune_sshtunnel' adapter",
            )

        return self

    def load(self) -> ITripleStorePort:
        if self.adapter != "custom":
            assert self.config is not None, "config is required"

            arguments = (
                self.config.model_dump()
                if not isinstance(self.config, dict)
                else self.config
            )

            # Lazy import: only import the adapter that's actually configured
            if self.adapter == "oxigraph":
                from naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph import (
                    Oxigraph,
                )

                OxigraphAdapterConfiguration.model_validate(arguments)

                return Oxigraph(**arguments)
            elif self.adapter == "aws_neptune":
                from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import (
                    AWSNeptune,
                )

                AWSNeptuneAdapterConfiguration.model_validate(arguments)

                return AWSNeptune(**arguments)
            elif self.adapter == "aws_neptune_sshtunnel":
                from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import (
                    AWSNeptuneSSHTunnel,
                )

                AWSNeptuneSSHTunnelAdapterConfiguration.model_validate(arguments)

                return AWSNeptuneSSHTunnel(**arguments)
            elif self.adapter == "fs":
                from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
                    TripleStoreService__SecondaryAdaptor__Filesystem,
                )

                TripleStoreAdapterFilesystemConfiguration.model_validate(arguments)

                return TripleStoreService__SecondaryAdaptor__Filesystem(**arguments)
            elif self.adapter == "object_storage":
                from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__ObjectStorage import (
                    TripleStoreService__SecondaryAdaptor__ObjectStorage,
                )

                return TripleStoreService__SecondaryAdaptor__ObjectStorage(**arguments)
            else:
                raise ValueError(f"Adapter {self.adapter} not supported")
        else:
            return super().load()


class TripleStoreServiceConfiguration(BaseModel):
    triple_store_adapter: TripleStoreAdapterConfiguration

    def load(self) -> TripleStoreService:
        return TripleStoreService(triple_store_adapter=self.triple_store_adapter.load())
