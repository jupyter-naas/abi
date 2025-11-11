from typing import Dict, Literal, Union

from abi.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from abi.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageServiceConfiguration,
)
from abi.services.triple_store.adaptors.secondary.AWSNeptune import (
    AWSNeptune,
    AWSNeptuneSSHTunnel,
)
from abi.services.triple_store.adaptors.secondary.Oxigraph import Oxigraph
from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
    TripleStoreService__SecondaryAdaptor__Filesystem,
)
from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__ObjectStorage import (
    TripleStoreService__SecondaryAdaptor__ObjectStorage,
)
from abi.services.triple_store.TripleStorePorts import ITripleStorePort
from abi.services.triple_store.TripleStoreService import TripleStoreService
from pydantic import BaseModel, model_validator
from typing_extensions import Self


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

    __MAPPING: Dict[
        Literal[
            "oxigraph",
            "aws_neptune_sshtunnel",
            "aws_neptune",
            "fs",
            "object_storage",
        ],
        type[ITripleStorePort],
    ] = {
        "oxigraph": Oxigraph,
        "aws_neptune_sshtunnel": AWSNeptuneSSHTunnel,
        "aws_neptune": AWSNeptune,
        "fs": TripleStoreService__SecondaryAdaptor__Filesystem,
        "object_storage": TripleStoreService__SecondaryAdaptor__ObjectStorage,
    }

    @model_validator(mode="after")
    def validate_adapter(self) -> Self:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        return self

    def load(self) -> ITripleStorePort:
        if self.adapter != "custom":
            if self.adapter not in self.__MAPPING:
                raise ValueError(f"Adapter {self.adapter} not supported")

            assert self.config is not None, "config is required"

            return self.__MAPPING[self.adapter](**self.config.model_dump())
        else:
            return super().load()


class TripleStoreServiceConfiguration(BaseModel):
    ontology_adapter: TripleStoreAdapterConfiguration

    def load(self) -> TripleStoreService:
        return TripleStoreService(ontology_adaptor=self.ontology_adapter.load())
