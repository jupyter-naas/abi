from typing import Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.email.EmailPorts import IEmailAdapter
from naas_abi_core.services.email.EmailService import EmailService
from pydantic import BaseModel, ConfigDict, model_validator


class EmailAdapterSMTPConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "localhost"
    port: int = 1025
    username: str | None = None
    password: str | None = None
    use_tls: bool = False
    use_ssl: bool = False
    timeout: int = 10


class EmailAdapterConfiguration(GenericLoader):
    adapter: Literal["smtp", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "EmailAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "smtp":
            pydantic_model_validator(
                EmailAdapterSMTPConfiguration,
                self.config,
                "Invalid configuration for services.email.email_adapter 'smtp' adapter",
            )

        return self

    def load(self) -> IEmailAdapter:
        if self.adapter == "smtp":
            assert self.config is not None, "config is required for smtp adapter"
            from naas_abi_core.services.email.adapters.secondary.SMTPAdapter import (
                SMTPAdapter,
            )

            return SMTPAdapter(**self.config)
        elif self.adapter == "custom":
            return super().load()
        else:
            raise ValueError(f"Unknown adapter: {self.adapter}")


class EmailServiceConfiguration(BaseModel):
    email_adapter: EmailAdapterConfiguration

    def load(self) -> EmailService:
        return EmailService(adapter=self.email_adapter.load())
