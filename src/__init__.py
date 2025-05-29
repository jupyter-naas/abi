from dotenv import dotenv_values
from abi.services.secret.Secret import Secret
from abi.services.secret.adaptors.secondary import (
    dotenv_secret_secondaryadaptor,
    NaasSecret,
    Base64Secret,
)
from abi.services.secret.SecretPorts import ISecretAdapter
from src.services import init_services
from src import cli
from src.__modules__ import get_modules
import yaml
from dataclasses import dataclass
from typing import List
from abi import logger
from abi.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory as ObjectStorageFactory,
)
import atexit
import os
import asyncio


@atexit.register
def shutdown_services():
    services.triple_store_service.__del__()


@dataclass
class PipelineConfig:
    name: str
    cron: str
    parameters: List[dict]


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
secrets = {}
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

logger.debug("Initializing services")
services = init_services(config, secret)

logger.debug("Loading modules")
modules = get_modules()


async def load_ontologies_async():
    """Load all ontologies asynchronously"""
    tasks = []
    for module in modules:
        # Loading ontologies
        for ontology in module.ontologies:
            # Create async task for each load_schema call
            task = asyncio.create_task(
                asyncio.to_thread(services.triple_store_service.load_schema, ontology)
            )
            tasks.append(task)

    # Wait for all tasks to complete
    if tasks:
        await asyncio.gather(*tasks)


# Run the async ontology loading
asyncio.run(load_ontologies_async())

logger.debug("Loading triggers")
for module in modules:
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


for module in modules:
    module.on_initialized()

for module in modules:
    module.load_agents()

if __name__ == "__main__":
    cli()
