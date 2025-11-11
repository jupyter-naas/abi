from typing import Dict, List, Literal, Union

from abi.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from abi.services.secret.adaptors.secondary.Base64Secret import Base64Secret
from abi.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
    DotenvSecretSecondaryAdaptor,
)
from abi.services.secret.adaptors.secondary.NaasSecret import NaasSecret
from abi.services.secret.Secret import Secret
from abi.services.secret.SecretPorts import ISecretAdapter
from pydantic import BaseModel


class Base64SecretConfiguration(BaseModel):
    secret_adapter: "SecretAdapterConfiguration"
    base64_secret_key: str

    def load(self) -> Base64Secret:
        return Base64Secret(self.secret_adapter.load(), self.base64_secret_key)


class NaasSecretConfiguration(BaseModel):
    naas_api_key: str
    naas_api_url: str


class DotenvSecretConfiguration(BaseModel):
    pass


class SecretAdapterConfiguration(GenericLoader):
    adapter: Literal["dotenv", "naas", "base64", "custom"]
    config: (
        Union[
            DotenvSecretConfiguration,
            NaasSecretConfiguration,
            Base64SecretConfiguration,
        ]
        | None
    ) = None

    _MAPPING: Dict[Literal["dotenv", "naas", "base64"], type[ISecretAdapter]] = {
        "dotenv": DotenvSecretSecondaryAdaptor,
        "naas": NaasSecret,
        "base64": Base64Secret,
    }

    def load(self) -> ISecretAdapter:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

            if self.adapter == "base64":
                assert isinstance(self.config, Base64SecretConfiguration), (
                    "config must be a DotenvSecretConfiguration if adapter is dotenv"
                )
                assert hasattr(self.config, "load"), (
                    "config must have a load method if adapter is base64"
                )
                return self.config.load()
            else:
                return self._MAPPING[self.adapter](**self.config.model_dump())
        else:
            return super().load()


class SecretServiceConfiguration(BaseModel):
    secret_adapters: List[SecretAdapterConfiguration]

    def load(self) -> Secret:
        return Secret(adapters=[adapter.load() for adapter in self.secret_adapters])
