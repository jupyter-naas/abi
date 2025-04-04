from abi.services.secret.Secret import Secret
from abi.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import DotenvSecretSecondaryAdaptor
from src.services import init_services
from src import cli
from src.__modules__ import get_modules
import yaml
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path

from lib.abi.services.object_storage.ObjectStorageFactory import ObjectStorageFactory

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
    def from_yaml(cls, yaml_path: str = "config.yaml") -> 'Config':
        try:
            with open(yaml_path, 'r') as file:
                data = yaml.safe_load(file)
                config_data = data['config']
                pipeline_configs = [
                    PipelineConfig(
                        name=p['name'],
                        cron=p['cron'],
                        parameters=p['parameters']
                    ) for p in data['pipelines']
                ]
                return cls(
                    workspace_id=config_data.get('workspace_id'),
                    storage_name=config_data.get('storage_name'),
                    github_project_repository=config_data['github_project_repository'],
                    github_support_repository=config_data['github_support_repository'], 
                    github_project_id=config_data['github_project_id'],
                    triple_store_path=config_data['triple_store_path'],
                    api_title=config_data['api_title'],
                    api_description=config_data['api_description'],
                    logo_path=config_data['logo_path'],
                    favicon_path=config_data['favicon_path'],
                    pipelines=pipeline_configs,
                    space_name=config_data.get('space_name')
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
                space_name=""
            )

secret = Secret(DotenvSecretSecondaryAdaptor())
config = Config.from_yaml()

services = init_services(config, secret)

# Loading Modules
modules = get_modules()

for module in modules:
    # Loading triggers
    for trigger in module.triggers:
        topic, event_type, callback = trigger
        services.triple_store_service.subscribe(topic, event_type, callback)

    # Loading ontologies
    for ontology in module.ontologies:
        services.triple_store_service.load_schema(ontology)

if __name__ == "__main__":
    cli()