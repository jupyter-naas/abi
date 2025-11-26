import os
from io import StringIO
from typing import List

import yaml
from abi import logger
from abi.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageServiceConfiguration,
)
from abi.engine.engine_configuration.EngineConfiguration_SecretService import (
    SecretServiceConfiguration,
)
from abi.engine.engine_configuration.EngineConfiguration_TripleStoreService import (
    TripleStoreServiceConfiguration,
)
from abi.engine.engine_configuration.EngineConfiguration_VectorStoreService import (
    VectorStoreServiceConfiguration,
)
from abi.services.secret.Secret import Secret
from jinja2 import Template
from pydantic import BaseModel, model_validator
from typing_extensions import Literal


class ServicesConfiguration(BaseModel):
    object_storage: ObjectStorageServiceConfiguration
    triple_store: TripleStoreServiceConfiguration
    vector_store: VectorStoreServiceConfiguration
    secret: SecretServiceConfiguration


class ApiConfiguration(BaseModel):
    title: str = "ABI API"
    description: str = "API for ABI, your Artifical Business Intelligence"
    logo_path: str = "assets/logo.png"
    favicon_path: str = "assets/favicon.ico"
    cors_origins: List[str] = ["http://localhost:9879"]


class FirstPassConfiguration(BaseModel):
    """This is a first pass configuration that is used to load the secret service.

    It is used to load the secret service before the other services are loaded.
    This is because the secret service needs to be loaded before the other services
    are loaded to be able to resolve the secrets.
    This is a first pass configuration that is used to load the secret service.
    """

    class FirstPassServicesConfiguration(BaseModel):
        secret: SecretServiceConfiguration

    services: FirstPassServicesConfiguration


class ModuleConfig(BaseModel):
    path: str | None = None
    module: str | None = None
    enabled: bool
    config: dict = {}

    @model_validator(mode="after")
    def validate_path_or_module(self):
        if self.path is None and self.module is None:
            raise ValueError("Either path or module must be provided")

        if self.path is None:
            assert self.module is not None, (
                "module must be provided if path is not provided"
            )
        if self.module is None:
            assert self.path is not None, (
                "path must be provided if module is not provided"
            )
        return self


class GlobalConfig(BaseModel):
    ai_mode: Literal["cloud", "local", "airgap"]


class EngineConfiguration(BaseModel):
    workspace_id: str
    storage_name: str
    github_repository: str
    github_project_id: int
    triple_store_path: str
    space_name: str

    api: ApiConfiguration

    services: ServicesConfiguration

    global_config: GlobalConfig

    modules: List[ModuleConfig]

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "EngineConfiguration":
        with open(yaml_path, "r") as file:
            return cls.from_yaml_content(file.read())

    @classmethod
    def from_yaml_content(cls, yaml_content: str) -> "EngineConfiguration":
        # First we do a pass with the minimal configuration to load the secret service.
        class SecretServiceWrapper:
            secret_service: Secret | None = None

            def __init__(self, secret_service: Secret | None = None):
                self.secret_service = secret_service

            def __getattr__(self, name):
                if self.secret_service is None:
                    return 0
                secret = self.secret_service.get(name)
                if secret is None:
                    raise ValueError(f"Secret {name} not found")
                return secret

            def get(self, key, default=None):
                return 0

        first_pass_data = yaml.safe_load(
            StringIO(Template(yaml_content).render(secret=SecretServiceWrapper()))
        )

        first_pass_configuration = FirstPassConfiguration(**first_pass_data)
        secret_service = first_pass_configuration.services.secret.load()

        # Here we can now template the yaml by using `yaml_content` and the secret service.
        # Using Jinja2 template engine.

        logger.debug("Yaml content: {yaml_content}")

        template = Template(yaml_content)
        templated_yaml = template.render(secret=SecretServiceWrapper(secret_service))

        logger.debug(f"Templated yaml: {templated_yaml}")

        data = yaml.safe_load(StringIO(templated_yaml))

        logger.debug(f"Data: {data}")

        return cls(**data)

    @classmethod
    def load_configuration(
        cls, configuration_yaml: str | None = None
    ) -> "EngineConfiguration":
        # This is useful for testing.
        if configuration_yaml is not None:
            return cls.from_yaml_content(configuration_yaml)

        logger.debug(f"Loading configuration from {os.getenv('ENV')}")

        if os.path.exists(f"config.{os.getenv('ENV')}.yaml"):
            return cls.from_yaml(f"config.{os.getenv('ENV')}.yaml")
        elif os.path.exists("config.yaml"):
            return cls.from_yaml("config.yaml")
        else:
            raise FileNotFoundError(
                "Configuration file not found. Please create a config.yaml file or config.{env}.yaml file."
            )


if __name__ == "__main__":
    config = EngineConfiguration.load_configuration()
    print(config)
