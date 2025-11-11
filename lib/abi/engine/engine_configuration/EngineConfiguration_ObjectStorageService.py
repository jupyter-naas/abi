from typing import Dict, Literal, Tuple, Union

from abi.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from abi.services.object_storage.ObjectStoragePort import IObjectStorageAdapter
from abi.services.object_storage.ObjectStorageService import ObjectStorageService
from pydantic import BaseModel, model_validator
from typing_extensions import Self


class ObjectStorageAdapterFSConfiguration(BaseModel):
    base_path: str


class ObjectStorageAdapterS3Configuration(BaseModel):
    bucket_name: str
    access_key_id: str
    secret_access_key: str
    base_prefix: str
    session_token: str | None = None


class ObjectStorageAdapterNaasConfiguration(BaseModel):
    naas_api_key: str
    workspace_id: str
    storage_name: str
    base_prefix: str = ""


class ObjectStorageAdapterConfiguration(GenericLoader):
    adapter: Literal["fs", "s3", "naas", "custom"]
    config: (
        Union[
            ObjectStorageAdapterFSConfiguration,
            ObjectStorageAdapterS3Configuration,
            ObjectStorageAdapterNaasConfiguration,
        ]
        | None
    ) = None

    __MAPPING: Dict[Literal["fs", "s3", "naas"], Tuple[str, str]] = {
        "fs": (
            "abi.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS",
            "ObjectStorageSecondaryAdapterFS",
        ),
        "s3": (
            "abi.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3",
            "ObjectStorageSecondaryAdapterS3",
        ),
        "naas": (
            "abi.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNaas",
            "ObjectStorageSecondaryAdapterNaas",
        ),
    }

    @model_validator(mode="after")
    def validate_adapter(self) -> Self:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        return self

    def load(self) -> IObjectStorageAdapter:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

            return GenericLoader(
                python_module=self.__MAPPING[self.adapter][0],
                module_callable=self.__MAPPING[self.adapter][1],
                custom_config=self.config.model_dump(),
            ).load()
        else:
            return super().load()


class ObjectStorageServiceConfiguration(BaseModel):
    object_storage_adapter: ObjectStorageAdapterConfiguration

    def load(self) -> ObjectStorageService:
        return ObjectStorageService(adapter=self.object_storage_adapter.load())
