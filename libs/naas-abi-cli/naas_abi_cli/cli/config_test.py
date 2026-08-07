"""Tests for `abi config init`.

The contract is narrow on purpose: the generated file must be the *smallest*
useful configuration, and it must actually load. Every section of a config.yaml
has an engine default, so the scaffold writes only the one a project starts by
editing — `modules` — and leaves the rest implied. A test that only checked
"the file exists" would not catch a regression that starts writing the defaults
back out.
"""

from __future__ import annotations

import os

import pytest
import yaml
from click.testing import CliRunner
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)

from .config import config


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _init(runner: CliRunner, *args: str):
    return runner.invoke(config, ["init", *args])


def test_init_writes_config_yaml_by_default(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = _init(runner)

        assert result.exit_code == 0, result.output
        assert os.path.exists("config.yaml")


def test_init_output_loads_as_an_engine_configuration(runner: CliRunner) -> None:
    """The whole point of the command: `abi config init` then `abi config
    validate` must pass with nothing else done in between."""
    with runner.isolated_filesystem():
        _init(runner)

        configuration = EngineConfiguration.from_yaml("config.yaml")

        # Every section the scaffold leaves out still resolves.
        assert configuration.global_config.ai_mode == "cloud"
        assert configuration.api.port == 9879
        adapters = configuration.services.secret.secret_adapters
        assert [a.adapter for a in adapters] == ["dotenv"]
        # The engine appends its own core modules to an empty list.
        assert {m.module for m in configuration.modules} == {
            "naas_abi_core.modules.templatablesparqlquery",
            "naas_abi_core.modules.bfo",
            "naas_abi_core.modules.cco",
        }


def test_init_writes_nothing_the_engine_already_defaults(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _init(runner)

        document = yaml.safe_load(open("config.yaml", encoding="utf-8"))

        assert set(document) == {"modules"}
        assert document["modules"] == []


def test_init_creates_a_dotenv_file_when_missing(runner: CliRunner) -> None:
    """The default secret service reads ./.env, so the file is where an API key
    goes with nothing else to configure."""
    with runner.isolated_filesystem():
        _init(runner)

        assert os.path.exists(".env")


def test_init_leaves_an_existing_dotenv_file_alone(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        with open(".env", "w", encoding="utf-8") as file:
            file.write("EXISTING=1\n")

        _init(runner)

        assert open(".env", encoding="utf-8").read() == "EXISTING=1\n"


def test_init_refuses_to_overwrite_an_existing_file(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        with open("config.yaml", "w", encoding="utf-8") as file:
            file.write("# hand written\n")

        result = _init(runner)

        assert result.exit_code != 0
        assert open("config.yaml", encoding="utf-8").read() == "# hand written\n"


def test_init_force_overwrites_an_existing_file(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        with open("config.yaml", "w", encoding="utf-8") as file:
            file.write("# hand written\n")

        result = _init(runner, "--force")

        assert result.exit_code == 0, result.output
        assert "# hand written" not in open("config.yaml", encoding="utf-8").read()


def test_init_writes_to_a_custom_path_and_creates_parents(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = _init(runner, "--configuration-file", "nested/config.local.yaml")

        assert result.exit_code == 0, result.output
        assert os.path.exists("nested/config.local.yaml")
        # The .env lands beside the config, which is where the engine runs from.
        assert os.path.exists("nested/.env")


def test_init_output_contains_no_jinja_expressions(runner: CliRunner) -> None:
    """config.yaml is Jinja-rendered before it is parsed, so a `{{ secret.X }}`
    left in the scaffold — even inside a comment — would prompt or hard-fail on
    the very first load."""
    with runner.isolated_filesystem():
        _init(runner)

        assert "{{" not in open("config.yaml", encoding="utf-8").read()
