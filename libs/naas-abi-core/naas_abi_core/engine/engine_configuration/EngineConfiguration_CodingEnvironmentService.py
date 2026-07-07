from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    ICodingEnvironmentAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)


class CodingEnvironmentAdapterCoderConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_url: str  # e.g. https://coder.example.com
    wildcard_access_url: str  # e.g. "*.coder.example.com"
    admin_token: str  # "{{ secret.CODER_ADMIN_TOKEN }}"
    organization: str = "default"
    default_template_id: str | None = None
    default_token_lifetime_seconds: int = 3600  # converted to ns at the wire (§5)
    workspace_autostop_ms: int = 3_600_000  # idle autostop / cost control (§4a)
    timeout: int = 30


class CodingEnvironmentAdapterCodeServerConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str  # public embeddable code-server URL, e.g. https://code-server.example.com


class CodingEnvironmentAdapterInMemoryConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CodingEnvironmentAdapterConfiguration(GenericLoader):
    adapter: Literal["coder", "code_server", "in_memory", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "CodingEnvironmentAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "coder":
            pydantic_model_validator(
                CodingEnvironmentAdapterCoderConfiguration,
                self.config,
                "Invalid configuration for services.coding_environment."
                "coding_environment_adapter 'coder' adapter",
            )
        elif self.adapter == "code_server":
            pydantic_model_validator(
                CodingEnvironmentAdapterCodeServerConfiguration,
                self.config,
                "Invalid configuration for services.coding_environment."
                "coding_environment_adapter 'code_server' adapter",
            )
        elif self.adapter == "in_memory":
            pydantic_model_validator(
                CodingEnvironmentAdapterInMemoryConfiguration,
                self.config or {},
                "Invalid configuration for services.coding_environment."
                "coding_environment_adapter 'in_memory' adapter",
            )

        return self

    def load(self) -> ICodingEnvironmentAdapter:
        if self.adapter == "coder":
            assert self.config is not None, "config is required for coder adapter"
            from naas_abi_core.services.coding_environment.adapters.secondary.CoderAdapter import (
                CoderAdapter,
            )

            return CoderAdapter(**self.config)
        elif self.adapter == "code_server":
            assert self.config is not None, "config is required for code_server adapter"
            from naas_abi_core.services.coding_environment.adapters.secondary.CodeServerComposeAdapter import (
                CodeServerComposeAdapter,
            )

            return CodeServerComposeAdapter(**self.config)
        elif self.adapter == "in_memory":
            from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
                InMemoryAdapter,
            )

            return InMemoryAdapter(**(self.config or {}))
        elif self.adapter == "custom":
            return super().load()
        else:
            raise ValueError(f"Unknown adapter: {self.adapter}")


class CodingEnvironmentServiceConfiguration(BaseModel):
    coding_environment_adapter: CodingEnvironmentAdapterConfiguration

    def load(self) -> CodingEnvironmentService:
        return CodingEnvironmentService(adapter=self.coding_environment_adapter.load())
