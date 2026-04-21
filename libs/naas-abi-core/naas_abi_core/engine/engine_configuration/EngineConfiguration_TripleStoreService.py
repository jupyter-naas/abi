from typing import TYPE_CHECKING, Any, Literal, Union

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_KeyValueService import (
    KeyValueServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStorePort
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from pydantic import BaseModel, ConfigDict, model_validator
from typing_extensions import Self

# Only import for type checking, not at runtime
if TYPE_CHECKING:
    pass


class OxigraphAdapterConfiguration(BaseModel):
    """Oxigraph adapter configuration.

    triple_store_adapter:
      adapter: "oxigraph"
      config:
        oxigraph_url: "http://localhost:7878"
        timeout: 60
    """

    model_config = ConfigDict(extra="forbid")

    oxigraph_url: str = "http://localhost:7878"
    timeout: int = 60


class ApacheJenaTDB2AdapterConfiguration(BaseModel):
    """Apache Jena Fuseki (TDB2) adapter configuration.

    triple_store_adapter:
      adapter: "apache_jena_tdb2"
      config:
        jena_tdb2_url: "http://localhost:3030/ds"
        timeout: 60
        # Optional: promote the intra-process threading.Lock to a distributed
        # write lock so concurrent writers across different processes/instances
        # are serialised via the key-value store.
        key_value_service:
          kv_adapter:
            adapter: "redis"
            config:
              redis_url: "redis://localhost:6379"
    """

    model_config = ConfigDict(extra="forbid")

    jena_tdb2_url: str = "http://localhost:3030/ds"
    timeout: int = 60
    key_value_service: KeyValueServiceConfiguration | None = None


class AWSNeptuneAdapterConfiguration(BaseModel):
    """AWS Neptune adapter configuration.

    triple_store_adapter:
      adapter: "aws_neptune"
      config:
        aws_region_name: "{{ secret.AWS_REGION }}"
        aws_access_key_id: "{{ secret.AWS_ACCESS_KEY_ID }}"
        aws_secret_access_key: "{{ secret.AWS_SECRET_ACCESS_KEY }}"
        db_instance_identifier: "{{ secret.AWS_NEPTUNE_DB_INSTANCE_IDENTIFIER }}"
    """

    model_config = ConfigDict(extra="forbid")

    aws_region_name: str
    aws_access_key_id: str
    aws_secret_access_key: str
    db_instance_identifier: str


class AWSNeptuneSSHTunnelAdapterConfiguration(AWSNeptuneAdapterConfiguration):
    """AWS Neptune SSH tunnel adapter configuration.

    triple_store_adapter:
      adapter: "aws_neptune_sshtunnel"
      config:
        aws_region_name: "{{ secret.AWS_REGION }}"
        aws_access_key_id: "{{ secret.AWS_ACCESS_KEY_ID }}"
        aws_secret_access_key: "{{ secret.AWS_SECRET_ACCESS_KEY }}"
        db_instance_identifier: "{{ secret.AWS_NEPTUNE_DB_INSTANCE_IDENTIFIER }}"
        bastion_host: "{{ secret.AWS_BASTION_HOST }}"
        bastion_port: "{{ secret.AWS_BASTION_PORT }}"
        bastion_user: "{{ secret.AWS_BASTION_USER }}"
        bastion_private_key: "{{ secret.AWS_BASTION_PRIVATE_KEY }}"
    """

    model_config = ConfigDict(extra="forbid")

    bastion_host: str
    bastion_port: int
    bastion_user: str
    bastion_private_key: str


class TripleStoreAdapterFilesystemConfiguration(BaseModel):
    """Filesystem adapter configuration.

    triple_store_adapter:
      adapter: "fs"
      config:
        store_path: "storage/triplestore"
        triples_path: "triples"
    """

    model_config = ConfigDict(extra="forbid")

    store_path: str
    triples_path: str = "triples"


class TripleStoreAdapterOxigraphEmbeddedConfiguration(BaseModel):
    """Embedded Oxigraph adapter configuration.

    triple_store_adapter:
      adapter: "oxigraph_embedded"
      config:
        store_path: "storage/triplestore/oxigraph"
        graph_base_iri: "http://ontology.naas.ai/graph/default"
    """

    model_config = ConfigDict(extra="forbid")

    store_path: str
    graph_base_iri: str = "http://ontology.naas.ai/graph/default"


class TripleStoreAdapterObjectStorageConfiguration(BaseModel):
    """Object storage adapter configuration.

    triple_store_adapter:
      adapter: "object_storage"
      config:
        object_storage_service: *object_storage_service
        triples_prefix: "triples"
    """

    model_config = ConfigDict(extra="forbid")

    object_storage_service: ObjectStorageServiceConfiguration
    triples_prefix: str = "triples"


class TripleStoreAdapterConfiguration(GenericLoader):
    adapter: Literal[
        "oxigraph",
        "apache_jena_tdb2",
        "aws_neptune_sshtunnel",
        "aws_neptune",
        "fs",
        "oxigraph_embedded",
        "object_storage",
        "custom",
    ]
    config: (
        Union[
            OxigraphAdapterConfiguration,
            ApacheJenaTDB2AdapterConfiguration,
            AWSNeptuneAdapterConfiguration,
            AWSNeptuneSSHTunnelAdapterConfiguration,
            TripleStoreAdapterFilesystemConfiguration,
            TripleStoreAdapterOxigraphEmbeddedConfiguration,
            TripleStoreAdapterObjectStorageConfiguration,
            dict,
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_adapter(self) -> Self:
        config_value = self.config
        payload: dict[str, Any] | None
        if isinstance(config_value, BaseModel):
            payload = config_value.model_dump()
        elif isinstance(config_value, dict):
            payload = config_value
        else:
            payload = None

        def _payload_for(model: type[BaseModel]) -> dict | None:
            if payload is None:
                return None
            if not isinstance(payload, dict):
                return payload
            allowed_fields = set(model.model_fields.keys())
            return {
                key: value for key, value in payload.items() if key in allowed_fields
            }

        if self.adapter != "custom":
            assert payload is not None, "config is required if adapter is not custom"

        if self.adapter == "fs":
            self.config = TripleStoreAdapterFilesystemConfiguration.model_validate(
                _payload_for(TripleStoreAdapterFilesystemConfiguration)
            )
            pydantic_model_validator(
                TripleStoreAdapterFilesystemConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'fs' adapter",
            )
        if self.adapter == "object_storage":
            self.config = TripleStoreAdapterObjectStorageConfiguration.model_validate(
                _payload_for(TripleStoreAdapterObjectStorageConfiguration)
            )
            pydantic_model_validator(
                TripleStoreAdapterObjectStorageConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'object_storage' adapter",
            )
        if self.adapter == "oxigraph_embedded":
            self.config = (
                TripleStoreAdapterOxigraphEmbeddedConfiguration.model_validate(
                    _payload_for(TripleStoreAdapterOxigraphEmbeddedConfiguration)
                )
            )
            pydantic_model_validator(
                TripleStoreAdapterOxigraphEmbeddedConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'oxigraph_embedded' adapter",
            )
        if self.adapter == "oxigraph":
            self.config = OxigraphAdapterConfiguration.model_validate(
                _payload_for(OxigraphAdapterConfiguration)
            )
            pydantic_model_validator(
                OxigraphAdapterConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'oxigraph' adapter",
            )
        if self.adapter == "apache_jena_tdb2":
            self.config = ApacheJenaTDB2AdapterConfiguration.model_validate(
                _payload_for(ApacheJenaTDB2AdapterConfiguration)
            )
            pydantic_model_validator(
                ApacheJenaTDB2AdapterConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'apache_jena_tdb2' adapter",
            )
        if self.adapter == "aws_neptune":
            self.config = AWSNeptuneAdapterConfiguration.model_validate(
                _payload_for(AWSNeptuneAdapterConfiguration)
            )
            pydantic_model_validator(
                AWSNeptuneAdapterConfiguration,
                self.config,
                "Invalid configuration for services.triple_store.triple_store_adapter 'aws_neptune' adapter",
            )
        if self.adapter == "aws_neptune_sshtunnel":
            self.config = AWSNeptuneSSHTunnelAdapterConfiguration.model_validate(
                _payload_for(AWSNeptuneSSHTunnelAdapterConfiguration)
            )
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
            elif self.adapter == "apache_jena_tdb2":
                from naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import (
                    ApacheJenaTDB2,
                )

                assert isinstance(self.config, ApacheJenaTDB2AdapterConfiguration)

                kv_service = (
                    self.config.key_value_service.load()
                    if self.config.key_value_service is not None
                    else None
                )

                return ApacheJenaTDB2(
                    jena_tdb2_url=self.config.jena_tdb2_url,
                    timeout=self.config.timeout,
                    key_value_service=kv_service,
                )
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
            elif self.adapter == "oxigraph_embedded":
                from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
                    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded,
                )

                TripleStoreAdapterOxigraphEmbeddedConfiguration.model_validate(
                    arguments
                )

                return TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(
                    **arguments
                )
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
