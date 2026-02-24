import os
import sys
from io import StringIO
from typing import List

import yaml
from jinja2 import Template
from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration_BusService import (
    BusAdapterConfiguration,
    BusServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Deploy import (
    DeployConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_KeyValueService import (
    KeyValueAdapterConfiguration,
    KeyValueServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageAdapterConfiguration,
    ObjectStorageAdapterFSConfiguration,
    ObjectStorageServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_SecretService import (
    DotenvSecretConfiguration,
    SecretAdapterConfiguration,
    SecretServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_TripleStoreService import (
    TripleStoreAdapterConfiguration,
    TripleStoreAdapterFilesystemConfiguration,
    TripleStoreServiceConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_VectorStoreService import (
    VectorStoreAdapterConfiguration,
    VectorStoreServiceConfiguration,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter
from pydantic import BaseModel, model_validator
from rich.prompt import Prompt
from typing_extensions import Literal, Self


class ServicesConfiguration(BaseModel):
    object_storage: ObjectStorageServiceConfiguration = (
        ObjectStorageServiceConfiguration(
            object_storage_adapter=ObjectStorageAdapterConfiguration(
                adapter="fs",
                config=ObjectStorageAdapterFSConfiguration(
                    base_path="storage/datastore"
                ),
            )
        )
    )
    triple_store: TripleStoreServiceConfiguration = TripleStoreServiceConfiguration(
        triple_store_adapter=TripleStoreAdapterConfiguration(
            adapter="fs",
            config=TripleStoreAdapterFilesystemConfiguration(
                store_path="storage/triplestore", triples_path="triples"
            ),
        )
    )
    vector_store: VectorStoreServiceConfiguration = VectorStoreServiceConfiguration(
        vector_store_adapter=VectorStoreAdapterConfiguration(
            adapter="qdrant_in_memory", config={}
        )
    )
    secret: SecretServiceConfiguration = SecretServiceConfiguration(
        secret_adapters=[
            SecretAdapterConfiguration(
                adapter="dotenv", config=DotenvSecretConfiguration()
            )
        ]
    )
    bus: BusServiceConfiguration = BusServiceConfiguration(
        bus_adapter=BusAdapterConfiguration(adapter="python_queue", config={})
    )  # Provide default if not supplied
    kv: KeyValueServiceConfiguration = KeyValueServiceConfiguration(
        kv_adapter=KeyValueAdapterConfiguration(adapter="python", config={})
    )


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
    api: ApiConfiguration

    deploy: DeployConfiguration | None = None

    services: ServicesConfiguration

    global_config: GlobalConfig

    modules: List[ModuleConfig]

    default_agent: str = "naas_abi AbiAgent"

    def ensure_default_modules(self) -> None:
        if not any(
            m.path == "naas_abi_core.modules.templatablesparqlquery"
            or m.module == "naas_abi_core.modules.templatablesparqlquery"
            for m in self.modules
        ):
            self.modules.append(
                ModuleConfig(
                    module="naas_abi_core.modules.templatablesparqlquery",
                    enabled=True,
                    config={},
                )
            )

    @model_validator(mode="after")
    def validate_modules(self) -> Self:
        self.ensure_default_modules()
        return self

    @classmethod
    def _load_bootstrap_dotenv_adapter_from_yaml_content(
        cls, yaml_content: str
    ) -> ISecretAdapter | None:
        raw_data = yaml.safe_load(StringIO(yaml_content))
        if not isinstance(raw_data, dict):
            return None

        services = raw_data.get("services")
        if not isinstance(services, dict):
            return None

        secret = services.get("secret")
        if not isinstance(secret, dict):
            return None

        secret_adapters = secret.get("secret_adapters")
        if not isinstance(secret_adapters, list):
            return None

        for secret_adapter in secret_adapters:
            if not isinstance(secret_adapter, dict):
                continue

            if secret_adapter.get("adapter") != "dotenv":
                continue

            config = secret_adapter.get("config")
            if not isinstance(config, dict):
                config = {}

            path = config.get("path", ".env")
            if not isinstance(path, str) or path.strip() == "":
                raise ValueError(
                    "Invalid dotenv secret adapter path in configuration. "
                    "Expected a non-empty string at services.secret.secret_adapters[].config.path."
                )

            from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
                DotenvSecretSecondaryAdaptor,
            )

            return DotenvSecretSecondaryAdaptor(path=path)

        return None

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "EngineConfiguration":
        with open(yaml_path, "r") as file:
            return cls.from_yaml_content(file.read())

    @classmethod
    def from_yaml_content(cls, yaml_content: str) -> "EngineConfiguration":
        bootstrap_dotenv_adapter = cls._load_bootstrap_dotenv_adapter_from_yaml_content(
            yaml_content
        )

        # First we do a pass with the minimal configuration to load the secret service.
        class SecretServiceWrapper:
            secret_service: Secret | None = None
            bootstrap_dotenv_adapter: ISecretAdapter | None = None

            def __init__(
                self,
                secret_service: Secret | None = None,
                bootstrap_dotenv_adapter: ISecretAdapter | None = None,
            ):
                self.secret_service = secret_service
                self.bootstrap_dotenv_adapter = bootstrap_dotenv_adapter

            def __getattr__(self, name):
                if self.secret_service is None:
                    # This rule is used only when doing the first pass configuration to load the secret service.

                    # First priority is to check the environment variables.
                    if name in os.environ:
                        return os.environ.get(name)

                    if self.bootstrap_dotenv_adapter is not None:
                        value = self.bootstrap_dotenv_adapter.get(name)
                        if value is not None:
                            return value

                    return (
                        f"Secret '{name}' not found while loading the secret service. "
                        "Please provide it via the environment variables or configured secret service."
                    )
                elif name in os.environ:
                    return os.environ.get(name)
                secret = self.secret_service.get(name)
                if secret is None:
                    if not sys.stdin.isatty():
                        raise ValueError(
                            f"Secret '{name}' not found and no TTY available to prompt. Please provide it via the configured secret service or environment."
                        )
                    value = Prompt.ask(
                        f"[bold yellow]Secret '{name}' not found.[/bold yellow] Please enter the value for [cyan]{name}[/cyan]",
                        password=False,
                    )
                    self.secret_service.set(name, value)
                    return value
                return secret

        first_pass_data = yaml.safe_load(
            StringIO(
                Template(yaml_content).render(
                    secret=SecretServiceWrapper(
                        bootstrap_dotenv_adapter=bootstrap_dotenv_adapter
                    )
                )
            )
        )

        first_pass_configuration = FirstPassConfiguration(**first_pass_data)
        secret_service = first_pass_configuration.services.secret.load()

        # Here we can now template the yaml by using `yaml_content` and the secret service.
        # Using Jinja2 template engine.

        logger.debug(f"Yaml content: {yaml_content}")

        template = Template(yaml_content)
        templated_yaml = template.render(secret=SecretServiceWrapper(secret_service))

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

        env = os.getenv("ENV")
        if not env and os.path.exists("config.yaml"):
            with open("config.yaml", "r") as file:
                config_yaml = file.read()

            bootstrap_dotenv_adapter = (
                cls._load_bootstrap_dotenv_adapter_from_yaml_content(config_yaml)
            )
            if bootstrap_dotenv_adapter is not None:
                env_from_bootstrap = bootstrap_dotenv_adapter.get("ENV")
                if env_from_bootstrap is not None:
                    env = str(env_from_bootstrap)

        # First we check the environment variable.
        if env and os.path.exists(f"config.{env}.yaml"):
            config_file = f"config.{env}.yaml"
        # If the config.{env}.yaml file is not found, we check the config.yaml file.
        elif os.path.exists("config.yaml"):
            config_file = "config.yaml"
        else:
            raise FileNotFoundError(
                "Configuration file not found. Please create a config.yaml file or config.{env}.yaml file."
            )

        logger.debug(f"Loading configuration from {config_file}")

        return cls.from_yaml(config_file)


if __name__ == "__main__":
    config = EngineConfiguration.load_configuration()
    print(config)
