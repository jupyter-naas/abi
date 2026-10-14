"""`abi new module`: remote (SDK) modules by default, in-engine on request."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
    load_dev_configuration,
)
from naas_abi_core.engine.nats_auth import module_key

from naas_abi_cli.cli.new.agent import _new_agent
from naas_abi_cli.cli.new.module import _new_module
from naas_abi_cli.cli.new.remote_module import (
    COMPOSE_OVERRIDE,
    Project,
    add_compose_service,
    add_dev_module,
)
from naas_abi_cli.cli.new.workflow import _new_workflow

_LIBS = Path(__file__).resolve().parents[4]
_CORE_IMPORT = re.compile(r"^\s*(from|import)\s+naas_abi_core\b", re.MULTILINE)

_NATS_CONFIG = """\
api:
  title: "demo"

nats:
  nats_url: "nats://abi:{{ secret.NATS_ABI_PASSWORD }}@127.0.0.1:4222"
  jwt_secret: "{{ secret.NATS_JWT_SECRET }}"
  discovery:
    project: "acme"

modules:
  - module: demo
    enabled: true
"""

_CLASSIC_CONFIG = """\
api:
  title: "demo"

modules:
  - module: demo
    enabled: true
"""


def _project(tmp_path: Path, *, nats: bool = True, compose: bool = True) -> Path:
    root = tmp_path / "demo"
    (root / "src").mkdir(parents=True)
    (root / "config.yaml").write_text(
        _NATS_CONFIG if nats else _CLASSIC_CONFIG, encoding="utf-8"
    )
    (root / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    if compose:
        (root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    return root


def _invoke(command, cwd: Path, *args: str):
    previous = os.getcwd()
    os.chdir(cwd)
    try:
        return CliRunner().invoke(command, list(args))
    finally:
        os.chdir(previous)


def _python_files(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.py"))


# =============================================================================
# In a project: src/<name>/, dev.modules, docker-compose.override.yml
# =============================================================================


def test_a_new_module_is_a_remote_module_in_the_project_src(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = _invoke(_new_module, root, "research")

    assert result.exit_code == 0, result.output
    package = root / "src" / "research"
    for name in (
        "__init__.py",
        "__main__.py",
        "jobs.py",
        "agents/ResearchAgent.py",
        "tests/module_test.py",
        "Dockerfile",
        "apps/research/manifest.json",
        "AGENTS.md",
    ):
        assert (package / name).is_file(), name
    init = (package / "__init__.py").read_text(encoding="utf-8")
    # Stable id: the project and module names.
    assert 'MODULE_ID = "demo.research"' in init
    assert "naas_abi_sdk" in init
    # The discovery project is the engine's, read from the config.
    assert 'DEFAULT_DISCOVERY_PROJECT = "acme"' in (package / "__main__.py").read_text()


def test_a_remote_module_never_imports_abi_core(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")

    for path in _python_files(root / "src" / "research"):
        assert not _CORE_IMPORT.search(path.read_text(encoding="utf-8")), path
    dockerfile = (root / "src" / "research" / "Dockerfile").read_text()
    assert "find_spec('naas_abi_core')" in dockerfile
    assert "naas-abi-sdk[agent,otel]" in dockerfile


def test_the_generated_module_passes_its_own_tests(tmp_path: Path) -> None:
    """Its tests include the check that importing it loads no naas_abi_core."""
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    path = [
        str(root / "src"),
        str(_LIBS / "naas-abi-sdk"),
        str(_LIBS / "naas-abi-proto"),
    ]

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            str(root / "src" / "research"),
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([*path, *sys.path])},
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_the_module_is_run_by_abi_dev_up_not_loaded_by_the_engine(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)

    _invoke(_new_module, root, "research")

    dev = load_dev_configuration(str(root / "config.yaml"))
    assert [(m.name, m.module, m.args, m.identity) for m in dev.modules] == [
        ("research", "research", [], "demo.research")
    ]
    config = yaml.safe_load((root / "config.yaml").read_text())
    # It registers itself through discovery.
    assert [m["module"] for m in config["modules"]] == ["demo"]


def test_the_module_gets_a_compose_service_in_the_override(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / ".env").write_text(f"NATS_JWT_SECRET={'s' * 48}\n")

    _invoke(_new_module, root, "research")

    service = yaml.safe_load((root / COMPOSE_OVERRIDE).read_text())["services"][
        "research"
    ]
    assert service["build"]["context"] == "./src/research"
    assert service["build"]["additional_contexts"] == {
        "abi_proto": "./.abi/libs/naas-abi-proto",
        "abi_sdk": "./.abi/libs/naas-abi-sdk",
    }
    assert (
        "ABI_NATS_URL=nats://module:${NATS_MODULE_PASSWORD}@nats:4222"
        in service["environment"]
    )
    assert "ABI_DISCOVERY_PROJECT=acme" in service["environment"]
    assert service["depends_on"] == {"abi": {"condition": "service_healthy"}}
    # It signs as its module id with its own key, never with the project secret.
    assert not any("NATS_JWT_SECRET" in item for item in service["environment"])
    assert (
        "ABI_MODULE_KEY=${ABI_MODULE_KEY_RESEARCH:?ABI_MODULE_KEY_RESEARCH is not in "
        ".env: abi module key demo.research}" in service["environment"]
    )
    env = dict(
        line.split("=", 1) for line in (root / ".env").read_text().splitlines() if "=" in line
    )
    assert env["ABI_MODULE_KEY_RESEARCH"] == module_key(
        env["NATS_JWT_SECRET"], "demo.research"
    )
    # docker-compose.yml, which --regenerate rewrites, is left alone.
    assert (root / "docker-compose.yml").read_text() == "services: {}\n"


def test_without_the_engines_secret_no_key_is_made_up(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = _invoke(_new_module, root, "research")

    assert result.exit_code == 0, result.output
    assert not (root / ".env").exists()
    assert "abi module key demo.research" in result.output


def test_a_second_module_joins_the_first(tmp_path: Path) -> None:
    root = _project(tmp_path)

    _invoke(_new_module, root, "research")
    result = _invoke(_new_module, root, "writer")

    assert result.exit_code == 0, result.output
    names = [m.name for m in load_dev_configuration(str(root / "config.yaml")).modules]
    assert names == ["research", "writer"]
    services = yaml.safe_load((root / COMPOSE_OVERRIDE).read_text())["services"]
    assert list(services) == ["research", "writer"]


def test_a_classic_project_gets_no_compose_service(tmp_path: Path) -> None:
    """Its Docker stack has no broker: the module would never start."""
    root = _project(tmp_path, nats=False)

    result = _invoke(_new_module, root, "research")

    assert result.exit_code == 0, result.output
    assert not (root / COMPOSE_OVERRIDE).exists()
    assert "migrate-to-nats" in result.output
    assert "research:" in result.output  # the snippet, to add by hand
    # `abi dev up` runs on NATS by default, so the dev entry is still added.
    assert [
        m.name for m in load_dev_configuration(str(root / "config.yaml")).modules
    ] == ["research"]


def test_without_a_compose_file_the_service_is_printed(tmp_path: Path) -> None:
    root = _project(tmp_path, compose=False)

    result = _invoke(_new_module, root, "research")

    assert not (root / COMPOSE_OVERRIDE).exists()
    assert "ABI_NATS_URL" in result.output


def test_in_engine_keeps_the_classic_template(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = _invoke(_new_module, root, "legacy", "--in-engine")

    assert result.exit_code == 0, result.output
    package = root / "src" / "legacy"
    assert "naas_abi_core" in (package / "__init__.py").read_text()
    assert (package / "workflows").is_dir() and (package / "pipelines").is_dir()
    assert "  - module: legacy" in result.output
    assert not (root / COMPOSE_OVERRIDE).exists()
    assert load_dev_configuration(str(root / "config.yaml")).modules == []


def test_local_is_an_alias_of_in_engine(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = _invoke(_new_module, root, "legacy", "--local")

    assert result.exit_code == 0, result.output
    assert "naas_abi_core" in (root / "src" / "legacy" / "__init__.py").read_text()


# =============================================================================
# Standalone repositories
# =============================================================================


def test_standalone_creates_a_repository_of_its_own(tmp_path: Path) -> None:
    result = _invoke(
        _new_module, tmp_path, "research", "--standalone", "--abi-ref", "v9"
    )

    assert result.exit_code == 0, result.output
    repo = tmp_path / "research"
    for name in (
        "pyproject.toml",
        "Dockerfile",
        ".gitignore",
        ".dockerignore",
        "README.md",
        "AGENTS.md",
        "src/research/__init__.py",
        "src/research/tests/module_test.py",
    ):
        assert (repo / name).is_file(), name
    project = tomllib.loads((repo / "pyproject.toml").read_text())
    assert project["project"]["dependencies"] == [
        (
            "naas-abi-proto @ git+https://github.com/jupyter-naas/abi.git@v9"
            "#subdirectory=libs/naas-abi-proto"
        ),
        (
            "naas-abi-sdk[agent,otel] @ git+https://github.com/jupyter-naas/abi.git@v9"
            "#subdirectory=libs/naas-abi-sdk"
        ),
    ]
    assert project["tool"]["hatch"]["metadata"]["allow-direct-references"] is True
    assert project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/research"
    ]
    dockerfile = (repo / "Dockerfile").read_text()
    assert "FROM python:3.12-slim" in dockerfile
    assert "find_spec('naas_abi_core')" in dockerfile
    assert 'ENTRYPOINT ["python", "-m", "research"]' in dockerfile
    for path in _python_files(repo):
        assert not _CORE_IMPORT.search(path.read_text(encoding="utf-8")), path


def test_outside_a_project_a_remote_module_is_standalone(tmp_path: Path) -> None:
    result = _invoke(_new_module, tmp_path, "research")

    assert result.exit_code == 0, result.output
    assert "standalone" in result.output
    assert (tmp_path / "research" / "pyproject.toml").is_file()


def test_standalone_pins_the_sdk_to_this_cli_release_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    """Never a moving branch: the SDK the module installs matches the CLI."""
    import importlib.metadata

    monkeypatch.setattr(
        importlib.metadata,
        "version",
        lambda name: "3.0.0" if name == "naas-abi-cli" else "0",
    )

    result = _invoke(_new_module, tmp_path, "research", "--standalone")

    assert result.exit_code == 0, result.output
    project = tomllib.loads((tmp_path / "research" / "pyproject.toml").read_text())
    for dependency in project["project"]["dependencies"]:
        assert "@ git+https://github.com/jupyter-naas/abi.git@naas-abi-cli-v3.0.0#" in dependency
        assert "@main" not in dependency


def test_standalone_and_in_engine_exclude_each_other(tmp_path: Path) -> None:
    result = _invoke(_new_module, tmp_path, "x", "--standalone", "--in-engine")

    assert result.exit_code != 0
    assert not (tmp_path / "x").exists()


# =============================================================================
# Subcommands inside each kind of module
# =============================================================================


def test_new_agent_in_a_remote_module_is_an_sdk_agent(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    agents = root / "src" / "research" / "agents"

    result = _invoke(_new_agent, agents, "Critic")

    assert result.exit_code == 0, result.output
    code = (agents / "CriticAgent.py").read_text()
    assert "naas_abi_sdk.agents" in code and not _CORE_IMPORT.search(code)
    assert "expose_agent" in result.output


def test_new_app_in_a_remote_module_says_how_nexus_serves_it(tmp_path: Path) -> None:
    from naas_abi_cli.cli.new.app import _new_app

    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    apps = root / "src" / "research" / "apps"

    result = _invoke(_new_app, apps, "reports")

    assert result.exit_code == 0, result.output
    assert (apps / "reports" / "manifest.json").is_file()
    assert "/app-html/remote/<module_id>/reports/" in result.output
    assert 'expose_app("reports", app)' in result.output


def test_new_agent_in_an_in_engine_module_is_a_core_agent(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "legacy", "--in-engine")
    agents = root / "src" / "legacy" / "agents"

    result = _invoke(_new_agent, agents, "Critic")

    assert result.exit_code == 0, result.output
    assert _CORE_IMPORT.search((agents / "CriticAgent.py").read_text())


@pytest.mark.parametrize(
    "scaffold", ["workflow", "pipeline", "integration", "orchestration"]
)
def test_core_scaffolds_are_refused_in_a_remote_module(
    tmp_path: Path, scaffold
) -> None:
    import importlib

    command = getattr(
        importlib.import_module(f"naas_abi_cli.cli.new.{scaffold}"), f"_new_{scaffold}"
    )
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"

    result = _invoke(command, package, "Thing")

    assert result.exit_code != 0
    assert "--in-engine" in result.output
    assert not list(package.glob("Thing*.py"))


def test_core_scaffolds_still_work_in_an_in_engine_module(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "legacy", "--in-engine")
    workflows = root / "src" / "legacy" / "workflows"

    result = _invoke(_new_workflow, workflows, "Thing")

    assert result.exit_code == 0, result.output
    assert (workflows / "ThingWorkflow.py").is_file()


# =============================================================================
# Editing config.yaml and the override file
# =============================================================================


def _modules(config: Path) -> list[str]:
    return [m.name for m in load_dev_configuration(str(config)).modules]


def test_dev_module_appends_a_dev_block_keeping_the_rest(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    original = 'api:\n  title: "{{ secret.TITLE }}"  # templated\nmodules: []\n'
    config.write_text(original)

    assert add_dev_module(config, "research", "research")

    assert config.read_text().startswith(original)
    assert _modules(config) == ["research"]


def test_dev_module_joins_an_existing_list(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        "dev:\n  modules:\n    - name: probe\n      module: probe\n"
        "      args: [x]\n\nmodules: []\n"
    )

    assert add_dev_module(config, "research", "research")
    assert add_dev_module(config, "research", "research")  # once only

    assert _modules(config) == ["probe", "research"]
    assert yaml.safe_load(config.read_text())["modules"] == []


def test_dev_module_adds_modules_to_a_bare_dev_block(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("dev:\n  # nothing yet\nmodules: []\n")

    assert add_dev_module(config, "research", "research")

    assert _modules(config) == ["research"]


def test_dev_module_leaves_a_shape_it_does_not_handle(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    original = "dev:\n  modules: []\nmodules: []\n"
    config.write_text(original)

    assert not add_dev_module(config, "research", "research")
    assert config.read_text() == original


def test_compose_service_merges_into_an_existing_override(tmp_path: Path) -> None:
    project = Project(tmp_path)
    (tmp_path / COMPOSE_OVERRIDE).write_text("services:\n  mine:\n    image: x\n")

    assert add_compose_service(project, "research", {"image": "y"})
    assert not add_compose_service(project, "research", {"image": "z"})

    services = yaml.safe_load((tmp_path / COMPOSE_OVERRIDE).read_text())["services"]
    assert services == {"mine": {"image": "x"}, "research": {"image": "y"}}


@pytest.mark.parametrize("standalone", [False, True])
def test_the_build_context_leaves_secrets_and_caches_out(
    tmp_path: Path, standalone: bool
) -> None:
    """A31: env files, keys, bytecode and local state never reach the builder."""
    if standalone:
        result = _invoke(_new_module, tmp_path, "research", "--standalone", "--abi-ref", "v9")
        ignore = tmp_path / "research" / ".dockerignore"
    else:
        root = _project(tmp_path)
        result = _invoke(_new_module, root, "research")
        ignore = root / "src" / "research" / ".dockerignore"
    assert result.exit_code == 0, result.output
    patterns = set(ignore.read_text().splitlines())
    for pattern in ("**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/*.py[cod]", ".venv", "storage/"):
        assert pattern in patterns, pattern
