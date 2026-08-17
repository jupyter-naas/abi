"""Every top-level section of a config.yaml is optional.

A project should only have to write down what it wants to change. These tests
pin that down section by section, including the one that used to be mandatory
even when a project wanted the obvious behaviour: `services.secret`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)

_CORE_MODULES = {
    "naas_abi_core.modules.templatablesparqlquery",
    "naas_abi_core.modules.bfo",
    "naas_abi_core.modules.cco",
}


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """An empty directory as the working directory.

    The dotenv adapter and the Jinja loader both resolve relative to the CWD,
    so the tests below have to own it rather than inherit the repo's.
    """
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def test_an_empty_configuration_is_valid(project_dir: Path) -> None:
    configuration = EngineConfiguration.from_yaml_content("")

    assert configuration.api.port == 9879
    assert configuration.global_config.ai_mode == "cloud"
    assert configuration.default_agent == "naas_abi AbiAgent"
    assert {m.module for m in configuration.modules} == _CORE_MODULES


def test_a_comment_only_configuration_is_valid(project_dir: Path) -> None:
    configuration = EngineConfiguration.from_yaml_content("# nothing here yet\n")

    assert configuration.global_config.ai_mode == "cloud"


def test_services_default_when_the_section_is_absent(project_dir: Path) -> None:
    configuration = EngineConfiguration.from_yaml_content("modules: []\n")

    services = configuration.services
    assert services.triple_store.triple_store_adapter.adapter == "oxigraph_embedded"
    assert services.object_storage.object_storage_adapter.adapter == "fs"
    assert services.bus.bus_adapter.adapter == "python_queue"
    assert [a.adapter for a in services.secret.secret_adapters] == ["dotenv"]


def test_global_config_ai_mode_can_still_be_set(project_dir: Path) -> None:
    configuration = EngineConfiguration.from_yaml_content(
        "global_config:\n  ai_mode: airgap\n"
    )

    assert configuration.global_config.ai_mode == "airgap"


def test_explicit_sections_win_over_the_defaults(project_dir: Path) -> None:
    configuration = EngineConfiguration.from_yaml_content(
        "api:\n  port: 1234\n  title: Custom\n"
    )

    assert configuration.api.port == 1234
    assert configuration.api.title == "Custom"
    # Untouched fields still fall back.
    assert configuration.api.host == "0.0.0.0"  # nosec B104 - asserting a default


def test_defaulted_secret_service_tolerates_a_missing_dotenv(
    project_dir: Path,
) -> None:
    """The dotenv adapter is implied, not requested — a project with no secrets
    has no .env and must still boot."""
    assert not os.path.exists(".env")

    configuration = EngineConfiguration.from_yaml_content("modules: []\n")

    assert configuration.services.secret.load() is not None


def test_defaulted_secret_service_reads_dotenv_when_present(
    project_dir: Path,
) -> None:
    (project_dir / ".env").write_text("SOME_TOKEN=from-dotenv\n", encoding="utf-8")

    configuration = EngineConfiguration.from_yaml_content(
        'api:\n  title: "{{ secret.SOME_TOKEN }}"\n'
    )

    assert configuration.api.title == "from-dotenv"


def test_a_configured_dotenv_adapter_still_fails_when_its_file_is_missing(
    project_dir: Path,
) -> None:
    """A path the project wrote down is a promise; a missing file there is a
    mistake worth reporting, not a default to shrug off."""
    yaml_content = (
        "services:\n"
        "  secret:\n"
        "    secret_adapters:\n"
        "      - adapter: dotenv\n"
        "        config:\n"
        '          path: "missing.env"\n'
    )

    with pytest.raises(FileNotFoundError):
        EngineConfiguration.from_yaml_content(yaml_content)
