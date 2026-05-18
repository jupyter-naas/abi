import importlib
import os

import click
import pydantic_core
import yaml

from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)


@click.group("config")
def config():
    pass


def _validate_modules(configuration: EngineConfiguration) -> None:
    errors: list[str] = []

    for module_config in configuration.modules:
        if not module_config.enabled:
            continue

        if module_config.module is None:
            # path-based modules are not importable via importlib here; skip.
            continue

        module_name = module_config.module

        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            errors.append(f"{module_name}: failed to import ({e})")
            continue

        if not hasattr(module, "ABIModule"):
            errors.append(f"{module_name}: missing ABIModule class")
            continue

        if not hasattr(module.ABIModule, "Configuration"):
            errors.append(f"{module_name}: ABIModule missing Configuration class")
            continue

        if not hasattr(module.ABIModule, "get_dependencies"):
            errors.append(f"{module_name}: ABIModule missing get_dependencies method")
            continue

        try:
            module.ABIModule.Configuration(
                global_config=configuration.global_config,
                **module_config.config,
            )
        except pydantic_core._pydantic_core.ValidationError as e:
            errors.append(f"{module_name}: invalid configuration ({e})")
            continue
        except Exception as e:
            errors.append(
                f"{module_name}: failed to instantiate Configuration ({e})"
            )
            continue

        print(f"  ✓ {module_name}")

    if errors:
        for err in errors:
            print(f"  ✗ {err}")
        raise click.ClickException(
            f"{len(errors)} module(s) failed validation"
        )


@config.command("validate")
@click.option("--configuration-file", type=str, required=False, default=None)
@click.option(
    "--modules",
    is_flag=True,
    default=False,
    help="Also validate that each enabled module is importable and its config is valid.",
)
def validate(configuration_file: str | None, modules: bool):
    configuration_content: str | None = None

    if configuration_file is not None:
        if not os.path.exists(configuration_file):
            raise FileNotFoundError(
                f"Configuration file {configuration_file} not found"
            )
        with open(configuration_file, "r") as file:
            configuration_content = file.read()

    configuration = EngineConfiguration.load_configuration(configuration_content)
    print("Configuration is valid")

    if modules:
        print("Validating modules...")
        _validate_modules(configuration)
        print("All enabled modules are valid")


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
