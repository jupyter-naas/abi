from abi.services.secret.Secret import Secret
from abi.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import DotenvSecretSecondaryAdaptor
from src import cli
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
    github_project_repository: str
    github_support_repository: str
    github_project_id: int
    ontology_store_path: str
    api_title: str
    api_description: str
    logo_path: str
    favicon_path: str
    pipelines: List[PipelineConfig]
    storage_name: str

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
                    github_project_repository=config_data['github_project_repository'],
                    github_support_repository=config_data['github_support_repository'], 
                    github_project_id=config_data['github_project_id'],
                    ontology_store_path=config_data['ontology_store_path'],
                    api_title=config_data['api_title'],
                    api_description=config_data['api_description'],
                    logo_path=config_data['logo_path'],
                    favicon_path=config_data['favicon_path'],
                    pipelines=pipeline_configs,
                    storage_name=config_data['storage_name']
                )
        except FileNotFoundError:
            return cls(
                workspace_id="",
                github_project_repository="",
                github_support_repository="",
                github_project_id=0,
                ontology_store_path="",
                api_title="",
                api_description="",
                logo_path="",
                favicon_path="",
                pipelines=[],
                storage_name=""
            )

secret = Secret(DotenvSecretSecondaryAdaptor())
config = Config.from_yaml()

object_storage = ObjectStorageFactory.ObjectStorageServiceNaas(
    naas_api_key=secret.get('NAAS_API_KEY'),
    workspace_id=config.workspace_id,
    storage_name=config.storage_name
)

if __name__ == "__main__":
    cli()