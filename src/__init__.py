from dotenv import load_dotenv
load_dotenv()
from dotenv import dotenv_values
from abi.services.secret.Secret import Secret
from abi.services.secret.adaptors.secondary import (
    dotenv_secret_secondaryadaptor,
    NaasSecret,
    Base64Secret,
)
from abi.services.secret.SecretPorts import ISecretAdapter
from src.services import init_services

from src.__modules__ import get_modules
import yaml
from dataclasses import dataclass
from typing import List
from abi import logger
from abi.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory as ObjectStorageFactory,
)
from abi.utils.LazyLoader import LazyLoader
import atexit
import os


@atexit.register
def shutdown_services():
    global services
    if services.is_loaded():
        services.triple_store_service.__del__()


@dataclass
class PipelineConfig:
    name: str
    cron: str
    parameters: List[dict]


@dataclass
class ModuleConfig:
    path: str
    enabled: bool


@dataclass
class Config:
    workspace_id: str
    storage_name: str
    github_project_repository: str
    github_support_repository: str
    github_project_id: int
    triple_store_path: str
    api_title: str
    api_description: str
    logo_path: str
    favicon_path: str
    pipelines: List[PipelineConfig]
    space_name: str
    cors_origins: List[str]
    modules: List[ModuleConfig]

    @classmethod
    def from_yaml(cls, yaml_path: str = "config.yaml") -> "Config":
        try:
            with open(yaml_path, "r") as file:
                data = yaml.safe_load(file)
                config_data = data["config"]
                pipeline_configs = [
                    PipelineConfig(
                        name=p["name"], cron=p["cron"], parameters=p["parameters"]
                    )
                    for p in data["pipelines"]
                ]
                module_configs = [
                    ModuleConfig(
                        path=m["path"], enabled=m["enabled"]
                    )
                    for m in data["modules"]
                ]
                return cls(
                    workspace_id=config_data.get("workspace_id"),
                    storage_name=config_data.get("storage_name"),
                    github_project_repository=config_data["github_project_repository"],
                    github_support_repository=config_data["github_support_repository"],
                    github_project_id=config_data["github_project_id"],
                    triple_store_path=config_data["triple_store_path"],
                    api_title=config_data["api_title"],
                    api_description=config_data["api_description"],
                    logo_path=config_data["logo_path"],
                    favicon_path=config_data["favicon_path"],
                    pipelines=pipeline_configs,
                    space_name=config_data.get("space_name"),
                    cors_origins=config_data.get("cors_origins"),
                    modules=module_configs,
                )
        except FileNotFoundError:
            return cls(
                workspace_id="",
                storage_name="",
                github_project_repository="",
                github_support_repository="",
                github_project_id=0,
                triple_store_path="",
                api_title="",
                api_description="",
                logo_path="",
                favicon_path="",
                pipelines=[],
                space_name="",
                cors_origins=[],
                modules=[],
            )


logger.debug("Loading config")
secrets_adapters: List[ISecretAdapter] = [
    dotenv_secret_secondaryadaptor.DotenvSecretSecondaryAdaptor()
]

naas_api_key = os.getenv("NAAS_API_KEY")
naas_api_url = os.getenv("NAAS_API_URL", None)

logger.debug(
    "Loading secrets into environment variables. Priority: Environment variables > .env > Naas Secrets"
)
secrets: dict = {}
if naas_api_key is not None:
    naas_secret_adapter = NaasSecret.NaasSecret(naas_api_key, naas_api_url)
    base64_adapter = Base64Secret.Base64Secret(
        naas_secret_adapter, os.environ.get("ABI_BASE64_SECRET_NAME", "abi_secrets")
    )
    abi_secrets = base64_adapter.list()

    if abi_secrets is not None and len(abi_secrets) > 0:
        logger.debug("Loading Secrets from Naas Secrets")
        for key, value in abi_secrets.items():
            if os.getenv(key) is None:
                secrets[key] = value
            else:
                logger.debug(f"Secret {key} already set in environment variables")
                secrets[key] = os.getenv(key)

    secrets_adapters.append(NaasSecret.NaasSecret(naas_api_key, naas_api_url))

logger.debug("Loading Secrets from .env file")
envfile_values = dotenv_values()
for key, value in envfile_values.items():
    if os.getenv(key) is None:
        secrets[key] = value
    else:
        logger.debug(f"Secret {key} already set in environment variables")

logger.debug("Applying secrets to environment variables.")

# Apply secrets to environment variables
for key, value in secrets.items():
    if value is not None:
        os.environ.setdefault(key, value)


secret = Secret(secrets_adapters)
config = Config.from_yaml()

modules_loaded = False

def load_modules():
    global services
    logger.debug("Loading modules")
    _modules = get_modules(config)

    logger.debug("Loading ontologies")
    ontology_filepaths = []

    for module in _modules:
        for ontology in module.ontologies:
            ontology_filepaths.append(ontology)
            
    services.triple_store_service.load_schemas(ontology_filepaths)

    logger.debug("Loading triggers")
    for module in _modules:
        # Loading triggers
        for trigger in module.triggers:
            if trigger is None:
                logger.warning(
                    f"None trigger found for module {module.module_import_path}."
                )
                continue
            if len(trigger) == 3:
                topic, event_type, callback = trigger
                services.triple_store_service.subscribe(topic, event_type, callback)
            elif len(trigger) == 4:
                topic, event_type, callback, background = trigger
                services.triple_store_service.subscribe(
                    topic, event_type, callback, background
                )


    for module in _modules:
        module.on_initialized()

    return _modules

services = LazyLoader(lambda: init_services(config, secret))
modules = LazyLoader(lambda: load_modules())


