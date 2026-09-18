from typing import Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    ISourceControlAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)
from pydantic import BaseModel, ConfigDict, model_validator


class SourceControlAdapterForgejoConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str  # e.g. https://forge.example.com
    admin_token: str  # "{{ secret.FORGEJO_ADMIN_TOKEN }}"
    organization: str = ""
    timeout: int = 30


class SourceControlAdapterInMemoryConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceControlAdapterLocalGitConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repos_root: str


class SourceControlAdapterNATSConfiguration(BaseModel):
    """Source control adapter NATS RPC client configuration.

    Talks to a remote ``SourceControlPrimaryAdapterNATS`` over NATS
    request/reply -- see docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md
    (Stage 1) and naas_abi_core/proto/source_control/v1/source_control.proto.

    source_control_adapter:
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


class SourceControlAdapterConfiguration(GenericLoader):
    adapter: Literal["forgejo", "in_memory", "local_git", "nats_rpc", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "SourceControlAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "forgejo":
            pydantic_model_validator(
                SourceControlAdapterForgejoConfiguration,
                self.config,
                "Invalid configuration for services.source_control."
                "source_control_adapter 'forgejo' adapter",
            )
        elif self.adapter == "in_memory":
            pydantic_model_validator(
                SourceControlAdapterInMemoryConfiguration,
                self.config or {},
                "Invalid configuration for services.source_control."
                "source_control_adapter 'in_memory' adapter",
            )
        elif self.adapter == "local_git":
            pydantic_model_validator(
                SourceControlAdapterLocalGitConfiguration,
                self.config,
                "Invalid configuration for services.source_control."
                "source_control_adapter 'local_git' adapter",
            )
        elif self.adapter == "nats_rpc":
            pydantic_model_validator(
                SourceControlAdapterNATSConfiguration,
                self.config,
                "Invalid configuration for services.source_control."
                "source_control_adapter 'nats_rpc' adapter",
            )

        return self

    def load(self) -> ISourceControlAdapter:
        if self.adapter == "forgejo":
            assert self.config is not None, "config is required for forgejo adapter"
            from naas_abi_core.services.source_control.adapters.secondary.ForgejoAdapter import (
                ForgejoAdapter,
            )

            return ForgejoAdapter(**self.config)
        elif self.adapter == "in_memory":
            from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
                InMemoryAdapter,
            )

            return InMemoryAdapter(**(self.config or {}))
        elif self.adapter == "local_git":
            assert self.config is not None, "config is required for local_git adapter"
            from naas_abi_core.services.source_control.adapters.secondary.LocalGitAdapter import (
                LocalGitAdapter,
            )

            return LocalGitAdapter(**self.config)
        elif self.adapter == "nats_rpc":
            assert self.config is not None, "config is required for nats_rpc adapter"
            from naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient import (
                SourceControlSecondaryAdapterNATSClient,
            )

            return SourceControlSecondaryAdapterNATSClient(**self.config)
        elif self.adapter == "custom":
            return super().load()
        else:
            raise ValueError(f"Unknown adapter: {self.adapter}")


class SourceControlServiceConfiguration(BaseModel):
    source_control_adapter: SourceControlAdapterConfiguration

    def load(self) -> SourceControlService:
        return SourceControlService(adapter=self.source_control_adapter.load())
