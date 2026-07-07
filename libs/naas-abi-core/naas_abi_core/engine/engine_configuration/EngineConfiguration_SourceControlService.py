from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

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


class SourceControlAdapterForgejoConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str  # e.g. https://forge.example.com
    admin_token: str  # "{{ secret.FORGEJO_ADMIN_TOKEN }}"
    organization: str = ""
    timeout: int = 30


class SourceControlAdapterInMemoryConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceControlAdapterConfiguration(GenericLoader):
    adapter: Literal["forgejo", "in_memory", "custom"]
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
        elif self.adapter == "custom":
            return super().load()
        else:
            raise ValueError(f"Unknown adapter: {self.adapter}")


class SourceControlServiceConfiguration(BaseModel):
    source_control_adapter: SourceControlAdapterConfiguration

    def load(self) -> SourceControlService:
        return SourceControlService(adapter=self.source_control_adapter.load())
