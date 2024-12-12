from abi.services.secret.Secret import Secret
from abi.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import DotenvSecretSecondaryAdaptor
from src import cli
import yaml
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

@dataclass
class PipelineConfig:
    name: str
    cron: str
    parameters: List[dict]

@dataclass
class Config:
    storage_name: Optional[str]
    workspace_id: Optional[str]
    workspace_name: Optional[str]
    github_support_repository: str
    github_project_id: int
    ontology_store_path: str
    pipelines: List[PipelineConfig]

    @classmethod
    def from_yaml(cls, yaml_path: str = "config.yaml") -> 'Config':
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
                storage_name=config_data.get('storage_name'),
                workspace_id=config_data.get('workspace_id'),
                workspace_name=config_data.get('workspace_name'),
                github_support_repository=config_data['github_support_repository'],
                github_project_id=config_data['github_project_id'],
                ontology_store_path=config_data['ontology_store_path'],
                pipelines=pipeline_configs
            )

secret = Secret(DotenvSecretSecondaryAdaptor())
config = Config.from_yaml()

if __name__ == "__main__":
    cli()