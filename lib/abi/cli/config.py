import os

import click
import yaml
from abi.engine.engine_configuration.EngineConfiguration import EngineConfiguration


@click.group("config")
def config():
    pass


@config.command("validate")
@click.option("--configuration-file", type=str, required=False, default=None)
def validate(configuration_file: str | None):
    configuration_content: str | None = None

    if configuration_file is not None:
        if not os.path.exists(configuration_file):
            raise FileNotFoundError(
                f"Configuration file {configuration_file} not found"
            )
        with open(configuration_file, "r") as file:
            configuration_content = file.read()

    EngineConfiguration.load_configuration(configuration_content)
    print("Configuration is valid")


@config.command("render")
@click.option("--configuration-file", type=str, required=False, default=None)
def render(configuration_file: str | None):
    configuration_content: str | None = None

    if configuration_file is not None:
        if not os.path.exists(configuration_file):
            raise FileNotFoundError(
                f"Configuration file {configuration_file} not found"
            )
        with open(configuration_file, "r") as file:
            configuration_content = file.read()

    configuration: EngineConfiguration = EngineConfiguration.load_configuration(
        configuration_content
    )
    print(yaml.dump(configuration.model_dump(), indent=2))
