import json
import subprocess
from uuid import uuid4

import click
import requests
from pydantic import BaseModel
from rich.console import Console
from rich.markdown import Markdown

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)


@click.group("deploy")
def deploy():
    pass


class Container(BaseModel):
    name: str
    image: str
    port: int
    cpu: str
    memory: str
    env: dict


class Space(BaseModel):
    name: str
    containers: list[Container]


class NaasAPIClient:
    naas_api_key: str
    base_url: str

    def __init__(self, naas_api_key: str):
        self.naas_api_key = naas_api_key
        self.base_url = "https://api.naas.ai"

    def create_registry(self, name: str):
        response = requests.post(
            f"{self.base_url}/registry/",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
            json={"name": name},
        )
        if response.status_code == 409:
            return self.get_registry(name)
        response.raise_for_status()
        return response.json()

    def get_registry(self, name: str):
        response = requests.get(
            f"{self.base_url}/registry/{name}",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
        )
        response.raise_for_status()
        return response.json()

    def get_registry_credentials(self, name: str):
        response = requests.get(
            f"{self.base_url}/registry/{name}/credentials",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
        )
        response.raise_for_status()
        return response.json()

    def update_space(self, space: Space) -> dict:
        response = requests.put(
            f"{self.base_url}/space/{space.name}",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
            json=space.model_dump(),
        )
        response.raise_for_status()
        return response.json()

    def create_space(self, space: Space) -> dict:
        response = requests.post(
            f"{self.base_url}/space/",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
            json=space.model_dump(),
        )

        if response.status_code == 409:
            return self.update_space(space)

        response.raise_for_status()
        return response.json()

    def get_space(self, name: str) -> dict:
        response = requests.get(
            f"{self.base_url}/space/{name}",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
        )
        response.raise_for_status()
        return response.json()


class NaasDeployer:
    image_name: str

    naas_api_client: NaasAPIClient

    def __init__(self, configuration: EngineConfiguration):
        self.configuration = configuration
        self.image_name = str(uuid4())
        assert configuration.deploy is not None
        self.naas_api_client = NaasAPIClient(configuration.deploy.naas_api_key)

    def docker_build(self, image_name: str):
        subprocess.run(
            f"docker build -t {image_name} . --platform linux/amd64", shell=True
        )

    def env_list_to_dict(self, env: list[str]) -> dict:
        return {env_var.split("=", 1)[0]: env_var.split("=", 1)[1] for env_var in env}

    def deploy(self, env: list[str]):
        
        registry = self.naas_api_client.create_registry(
            self.configuration.deploy.space_name
        )

        uid = str(uuid4())

        image_name = f"{registry['registry']['uri']}:{uid}"
        self.docker_build(image_name)
        credentials = self.naas_api_client.get_registry_credentials(
            self.configuration.deploy.space_name
        )
        docker_login_command = f"docker login -u {credentials['credentials']['username']} -p {credentials['credentials']['password']} {registry['registry']['uri']}"
        subprocess.run(docker_login_command, shell=True)
        subprocess.run(f"docker push {image_name}", shell=True)

        image_sha = (
            subprocess.run(
                "docker inspect --format='{{index .RepoDigests 0}}' "
                + image_name
                + " | cut -d'@' -f2",
                shell=True,
                capture_output=True,
            )
            .stdout.strip()
            .decode("utf-8")
        )

        image_name_with_sha = f"{image_name.replace(':' + uid, '')}@{image_sha}"


        self.naas_api_client.create_space(
            Space(
                name=self.configuration.deploy.space_name,
                containers=[
                    Container(
                        name="api",
                        image=image_name_with_sha,
                        port=9879,
                        cpu="1",
                        memory="1Gi",
                        # env=self.env_list_to_dict(env) | {
                        #     "NAAS_API_KEY": self.configuration.deploy.naas_api_key,
                        #     "ENV": "prod",
                        # },
                        env=self.configuration.deploy.env | self.env_list_to_dict(env),
                    )
                ],
            )
        )

        space = self.naas_api_client.get_space(self.configuration.deploy.space_name)

        Console().print(
            Markdown(f"""
# Deployment successful

- Space: {self.configuration.deploy.space_name}
- Image: {image_name_with_sha}
- URL: https://{self.configuration.deploy.space_name}.default.space.naas.ai

                                 """)
        )


@deploy.command("naas")
@click.option("-e", "--env", multiple=True, help="Environment variables to set (e.g. -e FOO=BAR -e BAZ=QUX)")
def naas(env: list[str]):
    configuration: EngineConfiguration = EngineConfiguration.load_configuration()

    if configuration.deploy is None:
        logger.error(
            "Deploy configuration not found in the yaml configuration file. Please add a deploy section to the configuration file."
        )

    deployer = NaasDeployer(configuration)
    deployer.deploy(env)
