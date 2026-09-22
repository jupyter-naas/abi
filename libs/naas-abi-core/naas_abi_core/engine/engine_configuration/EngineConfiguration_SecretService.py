from typing import TYPE_CHECKING, Literal, Self

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter
from pydantic import BaseModel, ConfigDict, model_validator

# Only import for type checking, not at runtime
if TYPE_CHECKING:
    from naas_abi_core.services.secret.adaptors.secondary.Base64Secret import (
        Base64Secret,
    )


class DotenvSecretConfiguration(BaseModel):
    """Dotenv secret configuration.

    secret_adapters:
      - adapter: "dotenv"
        config:
          path: ".env"
    """

    model_config = ConfigDict(extra="forbid")

    path: str = ".env"


class NaasSecretConfiguration(BaseModel):
    """Naas secret configuration.

    secret_adapters:
      - adapter: "naas"
        config:
          naas_api_key: "{{ secret.NAAS_API_KEY }}"
          naas_api_url: "https://api.naas.ai"
    """

    model_config = ConfigDict(extra="forbid")

    naas_api_key: str
    naas_api_url: str


class Base64SecretConfiguration(BaseModel):
    """Base64 secret configuration.

    secret_adapters:
      - adapter: "base64"
        config:
          secret_adapter: *secret_adapter
          base64_secret_key: "{{ secret.BASE64_SECRET_KEY }}"
    """

    model_config = ConfigDict(extra="forbid")

    secret_adapter: "SecretAdapterConfiguration"
    base64_secret_key: str

    def load(self) -> "Base64Secret":
        from naas_abi_core.services.secret.adaptors.secondary.Base64Secret import (
            Base64Secret,
        )

        return Base64Secret(self.secret_adapter.load(), self.base64_secret_key)


class SecretAdapterNATSConfiguration(BaseModel):
    """Secret adapter NATS RPC client configuration.

    Talks to a remote ``SecretPrimaryAdapterNATS`` over NATS request/reply
    -- see docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md
    (Stage 1) and naas_abi_core/proto/secret/v1/secret.proto.

    Security note: Stage 1's shared-JWT auth has no per-caller
    authorization -- anyone holding a valid service token can read every
    secret the remote process exposes. Accepted as a known, temporary
    Stage 1 gap, not an oversight -- revisit once Stage 2 per-caller
    authorization exists.

    Plugs into the existing multi-adapter fan-out exactly like dotenv/naas/
    base64 already do -- add it as one more entry in secret_adapters, not
    a top-level swap:

    secret_adapters:
      - adapter: "nats_rpc"
        config:
          nats_url: "nats://127.0.0.1:4222"
          jwt_secret: "{{ secret.NATS_SERVICE_JWT_SECRET }}"
          service_identity: "api"
    """
    model_config = ConfigDict(extra="forbid")

    nats_url: str = "nats://127.0.0.1:4222"
    jwt_secret: str
    service_identity: str = "api"


class SecretAdapterConfiguration(GenericLoader):
    adapter: Literal["dotenv", "naas", "base64", "nats_rpc", "custom"]
    config: (
        DotenvSecretConfiguration | NaasSecretConfiguration | Base64SecretConfiguration
        | SecretAdapterNATSConfiguration | None
    ) = None

    @model_validator(mode="after")
    def validate_adapter(self) -> Self:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )
        if self.adapter == "base64":
            pydantic_model_validator(
                Base64SecretConfiguration,
                self.config,
                "Invalid configuration for services.secret.secret_adapters 'base64' adapter",
            )
        if self.adapter == "dotenv":
            pydantic_model_validator(
                DotenvSecretConfiguration,
                self.config,
                "Invalid configuration for services.secret.secret_adapters 'dotenv' adapter",
            )
        if self.adapter == "naas":
            pydantic_model_validator(
                NaasSecretConfiguration,
                self.config,
                "Invalid configuration for services.secret.secret_adapters 'naas' adapter",
            )
        if self.adapter == "nats_rpc":
            pydantic_model_validator(
                SecretAdapterNATSConfiguration,
                self.config,
                "Invalid configuration for services.secret.secret_adapters 'nats_rpc' adapter",
            )
        return self

    def load(self) -> ISecretAdapter:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

            # Lazy import: only import the adapter that's actually configured
            if self.adapter == "base64":
                assert isinstance(self.config, Base64SecretConfiguration), (
                    "config must be a Base64SecretConfiguration if adapter is base64"
                )
                assert hasattr(self.config, "load"), (
                    "config must have a load method if adapter is base64"
                )
                return self.config.load()
            elif self.adapter == "dotenv":
                from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
                    DotenvSecretSecondaryAdaptor,
                )

                return DotenvSecretSecondaryAdaptor(**self.config.model_dump())
            elif self.adapter == "naas":
                from naas_abi_core.services.secret.adaptors.secondary.NaasSecret import (
                    NaasSecret,
                )

                return NaasSecret(**self.config.model_dump())
            else:
                raise ValueError(f"Unknown adapter: {self.adapter}")
        else:
            return super().load()


class SecretServiceConfiguration(BaseModel):
    secret_adapters: list[SecretAdapterConfiguration]

    def load(self) -> Secret:
        return Secret(adapters=[adapter.load() for adapter in self.secret_adapters])
