from typing import Dict, Literal, Tuple, Union

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import \
    GenericLoader
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import \
    pydantic_model_validator
from naas_abi_core.services.object_storage.ObjectStoragePort import \
    IObjectStorageAdapter
from naas_abi_core.services.object_storage.ObjectStorageService import \
    ObjectStorageService
from pydantic import BaseModel, ConfigDict, model_validator
from typing_extensions import Self


class ObjectStorageAdapterFSConfiguration(BaseModel):
    """Object storage adapter filesystem configuration.

    object_storage_adapter:
      adapter: "fs"
      config:
        base_path: "storage/datastore"
    """
    model_config = ConfigDict(extra="forbid")

    base_path: str


class ObjectStorageAdapterS3Configuration(BaseModel):
    """Object storage adapter S3 configuration.

    object_storage_adapter:
      adapter: "s3"
      config:
        bucket_name: "my-bucket"
        base_prefix: "my-prefix"
        access_key_id: "{{ secret.AWS_ACCESS_KEY_ID }}"
        secret_access_key: "{{ secret.AWS_SECRET_ACCESS_KEY }}"
        session_token: "{{ secret.AWS_SESSION_TOKEN }}"
        endpoint_url: "http://localhost:9000"
    """
    model_config = ConfigDict(extra="forbid")

    bucket_name: str
    base_prefix: str
    access_key_id: str
    secret_access_key: str
    session_token: str | None = None
    endpoint_url: str | None = None


class ObjectStorageAdapterNaasConfiguration(BaseModel):
    """Object storage adapter Naas configuration.

    object_storage_adapter:
      adapter: "naas"
      config:
        naas_api_key: "{{ secret.NAAS_API_KEY }}"
        workspace_id: "{{ secret.WORKSPACE_ID }}"
        storage_name: "{{ secret.STORAGE_NAME }}"
        base_prefix: "my-prefix"
    """
    model_config = ConfigDict(extra="forbid")

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

        if self.adapter == "fs":
            pydantic_model_validator(
                ObjectStorageAdapterFSConfiguration,
                self.config,
                "Invalid configuration for services.object_storage.object_storage_adapter 'fs' adapter",
            )
        if self.adapter == "s3":
            pydantic_model_validator(
                ObjectStorageAdapterS3Configuration,
                self.config,
                "Invalid configuration for services.object_storage.object_storage_adapter 's3' adapter",
            )
        if self.adapter == "naas":
            pydantic_model_validator(
                ObjectStorageAdapterNaasConfiguration,
                self.config,
                "Invalid configuration for services.object_storage.object_storage_adapter 'naas' adapter",
            )

        return self

    def load(self) -> IObjectStorageAdapter:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

            if self.adapter == "fs":
                from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import \
                    ObjectStorageSecondaryAdapterFS

                return ObjectStorageSecondaryAdapterFS(**self.config.model_dump())
            elif self.adapter == "s3":
                from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3 import \
                    ObjectStorageSecondaryAdapterS3

                return ObjectStorageSecondaryAdapterS3(**self.config.model_dump())
            elif self.adapter == "naas":
                from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNaas import \
                    ObjectStorageSecondaryAdapterNaas

                return ObjectStorageSecondaryAdapterNaas(**self.config.model_dump())
            else:
                raise ValueError(f"Unknown adapter: {self.adapter}")
            # return GenericLoader(
            #     python_module=self.__MAPPING[self.adapter][0],
            #     module_callable=self.__MAPPING[self.adapter][1],
            #     custom_config=self.config.model_dump(),
            # ).load()
        else:
            return super().load()


class ObjectStorageServiceConfiguration(BaseModel):
    object_storage_adapter: ObjectStorageAdapterConfiguration

    def load(self) -> ObjectStorageService:
        return ObjectStorageService(adapter=self.object_storage_adapter.load())
