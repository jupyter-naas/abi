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
    MIGRATE_TO_NATS_DOC,
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
        "ontologies/AGENTS.md",
        "ontologies/modules/ResearchOntology.ttl",
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
    assert "naas-abi-sdk[agent,otel,workflows,rdf]" in dockerfile


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="generated modules need Python 3.12 (projects and their images do)",
)
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


def test_the_compose_service_joins_the_discovery_project_of_the_docker_config(
    tmp_path: Path,
) -> None:
    # A project moved to NATS by hand names its discovery project in the config
    # the Docker engine reads; config.yaml (`abi dev up`) may not name one.
    root = _project(tmp_path, nats=False)
    (root / "config.local.yaml").write_text(
        _NATS_CONFIG.replace('"acme"', '"acme_stack"'), encoding="utf-8"
    )
    (root / ".env").write_text(f"NATS_JWT_SECRET={'s' * 48}\n")

    _invoke(_new_module, root, "research")

    service = yaml.safe_load((root / COMPOSE_OVERRIDE).read_text())["services"][
        "research"
    ]
    assert "ABI_DISCOVERY_PROJECT=acme_stack" in service["environment"]


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


def test_a_classic_project_gets_an_in_engine_module_by_default(
    tmp_path: Path,
) -> None:
    """Nothing runs a remote module without NATS: neither `abi dev up`
    in-process nor the classic Docker stack, which has no broker."""
    root = _project(tmp_path, nats=False)

    result = _invoke(_new_module, root, "research")

    assert result.exit_code == 0, result.output
    assert "naas_abi_core" in (root / "src" / "research" / "__init__.py").read_text()
    assert "  - module: research" in result.output
    assert "--remote" in result.output
    assert load_dev_configuration(str(root / "config.yaml")).modules == []


def test_a_project_on_nats_natively_gets_a_remote_module(tmp_path: Path) -> None:
    """The guide puts the `nats:` block in config.yaml for `abi dev up`; the
    Docker config (config.local.yaml) may stay classic."""
    root = _project(tmp_path, nats=True)
    (root / "config.local.yaml").write_text(_CLASSIC_CONFIG, encoding="utf-8")

    result = _invoke(_new_module, root, "research")

    assert result.exit_code == 0, result.output
    assert "naas_abi_sdk" in (root / "src" / "research" / "__init__.py").read_text()
    assert [
        m.name for m in load_dev_configuration(str(root / "config.yaml")).modules
    ] == ["research"]
    # Its Docker stack has no broker: the service is printed, not added.
    assert not (root / COMPOSE_OVERRIDE).exists()
    assert "Docker config has no `nats:` block" in result.output


def test_a_remote_module_in_a_classic_project_gets_no_compose_service(
    tmp_path: Path,
) -> None:
    """Its Docker stack has no broker: the module would never start."""
    root = _project(tmp_path, nats=False)

    result = _invoke(_new_module, root, "research", "--remote")

    assert result.exit_code == 0, result.output
    assert not (root / COMPOSE_OVERRIDE).exists()
    assert MIGRATE_TO_NATS_DOC in result.output
    assert "research:" in result.output  # the snippet, to add by hand
    # Ready for `abi dev up` once the project is on NATS.
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
            "naas-abi-sdk[agent,otel,workflows,rdf] @ git+https://github.com/jupyter-naas/abi.git@v9"
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


def test_remote_and_in_engine_exclude_each_other(tmp_path: Path) -> None:
    result = _invoke(_new_module, tmp_path, "x", "--remote", "--in-engine")

    assert result.exit_code == 2
    assert "drop --in-engine" in result.output


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
    # The agent can take the module's workflow and pipeline tools.
    import ast

    (create,) = [
        node
        for node in ast.parse(code).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_agent"
    ]
    assert "tools" in [arg.arg for arg in create.args.kwonlyargs]


def test_new_app_in_a_remote_module_says_how_nexus_serves_it(tmp_path: Path) -> None:
    from naas_abi_cli.cli.new.app import _new_app

    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    apps = root / "src" / "research" / "apps"

    result = _invoke(_new_app, apps, "reports")

    assert result.exit_code == 0, result.output
    assert (apps / "reports" / "manifest.json").is_file()
    # The module's name, not the placeholder, in what the scaffold writes.
    for written in (apps / "reports" / "manifest.json", apps / "AGENTS.md"):
        text = written.read_text()
        assert "research" in text and "your_module_name" not in text
    assert "  - module: research\n" in (apps / "AGENTS.md").read_text()
    assert "/app-html/remote/<module_id>/reports/" in result.output
    assert 'expose_app("reports", app)' in result.output

    # A second app keeps the AGENTS.md the module's author has since edited.
    (apps / "AGENTS.md").write_text("hand-written notes\n")
    assert _invoke(_new_app, apps, "charts").exit_code == 0
    assert (apps / "AGENTS.md").read_text() == "hand-written notes\n"
    assert "research" in (apps / "charts" / "manifest.json").read_text()


def test_new_app_in_a_nested_module_names_its_dotted_package(tmp_path: Path) -> None:
    from naas_abi_cli.cli.new.app import _new_app

    core = tmp_path / "src" / "core"
    research = core / "research"
    research.mkdir(parents=True)
    (core / "__init__.py").write_text("")
    (research / "__init__.py").write_text("class ABIModule(BaseModule):\n    pass\n")
    apps = research / "apps"
    apps.mkdir()

    assert _invoke(_new_app, apps, "reports").exit_code == 0

    assert "the core.research module" in (apps / "reports" / "manifest.json").read_text()
    for written in (apps / "AGENTS.md", apps / "reports" / "README.md"):
        assert "  - module: core.research\n" in written.read_text()


def test_new_agent_in_an_in_engine_module_is_a_core_agent(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "legacy", "--in-engine")
    agents = root / "src" / "legacy" / "agents"

    result = _invoke(_new_agent, agents, "Critic")

    assert result.exit_code == 0, result.output
    assert _CORE_IMPORT.search((agents / "CriticAgent.py").read_text())


def test_orchestration_is_refused_in_a_remote_module(tmp_path: Path) -> None:
    from naas_abi_cli.cli.new.orchestration import _new_orchestration

    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"

    result = _invoke(_new_orchestration, package, "Thing")

    assert result.exit_code != 0
    assert "--in-engine" in result.output and "@job" in result.output
    assert not list(package.glob("Thing*.py"))


_SCAFFOLDS = [
    ("workflow", "_new_workflow", "workflows", "ThingWorkflow", "thing_workflow"),
    ("pipeline", "_new_pipeline", "pipelines", "ThingPipeline", "thing_pipeline"),
    ("integration", "_new_integration", "integrations", "ThingIntegration", None),
]


def _scaffold(kind: str, package: Path, folder: str, name: str = "Thing"):
    import importlib

    command = getattr(
        importlib.import_module(f"naas_abi_cli.cli.new.{kind}"), f"_new_{kind}"
    )
    return _invoke(command, package, name, folder)


def test_a_remote_module_has_folders_for_its_components(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"

    for folder in ("workflows", "pipelines", "integrations"):
        assert (package / folder / "__init__.py").is_file(), folder
        notes = (package / folder / "AGENTS.md").read_text()
        assert "naas_abi_sdk" in notes and "naas_abi_core" in notes
        assert f"abi new {folder.removesuffix('s')}" in notes
        assert f"`{folder}/`" in (package / "AGENTS.md").read_text()
    guide = (package / "AGENTS.md").read_text()
    assert "expose_workflow" in guide and "expose_pipeline" in guide


@pytest.mark.parametrize(("kind", "_command", "folder", "cls", "slug"), _SCAFFOLDS)
def test_a_remote_scaffold_is_sdk_code_with_its_test(
    tmp_path: Path, kind, _command, folder, cls, slug
) -> None:
    import ast

    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"

    result = _scaffold(kind, package, folder)

    assert result.exit_code == 0, result.output
    assert "naas_abi_sdk" in result.output
    if slug:
        assert f"'{slug}'" in result.output
        # An agent built in on_initialized needs the instances built first.
        assert "build_processes()" in result.output
        assert "build_processes()" in (package / folder / f"{cls}.py").read_text()
    for written in (
        package / folder / f"{cls}.py",
        package / folder / f"{cls}_test.py",
    ):
        code = written.read_text()
        ast.parse(code)
        assert not _CORE_IMPORT.search(code), written
        assert "naas_abi_core" not in code.replace("naas_abi_core)", "")
        assert "{{" not in code and "your_module_name" not in code
    assert f"naas_abi_sdk.{kind}" in (package / folder / f"{cls}.py").read_text()


def test_a_scaffold_in_a_subfolder_makes_it_a_package(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"

    result = _scaffold("workflow", package, "workflows/crm")

    assert result.exit_code == 0, result.output
    assert (package / "workflows" / "crm" / "__init__.py").is_file()
    assert (package / "workflows" / "crm" / "ThingWorkflow.py").is_file()


def _scaffold_at(kind: str, cwd: Path, *args: str):
    import importlib

    command = getattr(
        importlib.import_module(f"naas_abi_cli.cli.new.{kind}"), f"_new_{kind}"
    )
    return _invoke(command, cwd, "Thing", *args)


@pytest.mark.parametrize(("kind", "_command", "folder", "cls", "_slug"), _SCAFFOLDS)
def test_a_scaffold_with_the_default_path_lands_where_discovery_looks(
    tmp_path: Path, kind, _command, folder, cls, _slug
) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"

    result = _scaffold_at(kind, package)

    assert result.exit_code == 0, result.output
    assert (package / folder / f"{cls}.py").is_file()
    assert not (package / f"{cls}.py").exists()
    assert f"Created {cls}.py (naas_abi_sdk)" in result.output


def test_a_scaffold_run_inside_its_folder_stays_there(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"
    (package / "workflows" / "crm").mkdir()

    result = _scaffold_at("workflow", package / "workflows" / "crm")

    assert result.exit_code == 0, result.output
    assert (package / "workflows" / "crm" / "ThingWorkflow.py").is_file()
    assert not (package / "workflows" / "workflows").exists()


def test_a_scaffold_outside_its_folder_warns_and_does_not_promise_a_build(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"

    result = _scaffold_at("workflow", package, "agents")

    assert result.exit_code == 0, result.output
    assert "Warning" in result.output and "workflows/" in result.output
    assert "builds it after on_initialized" not in result.output
    assert (package / "agents" / "ThingWorkflow.py").is_file()


def test_a_scaffold_keeps_an_existing_package_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"
    (package / "workflows" / "__init__.py").write_text("# mine\n")

    _scaffold("workflow", package, "workflows")

    assert (package / "workflows" / "__init__.py").read_text() == "# mine\n"


def test_scaffolds_in_a_standalone_module_are_sdk_code_too(tmp_path: Path) -> None:
    repository = tmp_path / "research"
    result = _invoke(_new_module, tmp_path, "research", "--standalone")
    assert result.exit_code == 0, result.output
    package = repository / "src" / "research"

    assert _scaffold("workflow", package, "workflows").exit_code == 0
    assert _scaffold("pipeline", package, "pipelines").exit_code == 0

    for path in _python_files(package):
        assert not _CORE_IMPORT.search(path.read_text(encoding="utf-8")), path


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="generated modules need Python 3.12 (projects and their images do)",
)
def test_a_module_with_every_scaffold_passes_its_own_tests_and_builds_them(
    tmp_path: Path,
) -> None:
    """The acceptance path: a new module, then each scaffold, then its tests (the
    module's own, which load no naas_abi_core, and the scaffolds'), then the module
    finds and builds the workflow and the pipeline, and an agent can call them."""
    root = _project(tmp_path)
    _invoke(_new_module, root, "research")
    package = root / "src" / "research"
    for kind, _command, folder, _cls, _slug in _SCAFFOLDS:
        assert _scaffold(kind, package, folder, "Foo").exit_code == 0
    assert _scaffold("workflow", package, "workflows/crm", "Baz").exit_code == 0
    path = [
        str(root / "src"),
        str(_LIBS / "naas-abi-sdk"),
        str(_LIBS / "naas-abi-proto"),
    ]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([*path, *sys.path])}

    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            str(package),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert tests.returncode == 0, tests.stdout + tests.stderr
    assert "passed" in tests.stdout and "FooWorkflow_test" not in tests.stderr

    code = """
import asyncio
from unittest.mock import AsyncMock, MagicMock

import research
from naas_abi_sdk import job_host, module as sdk_module
from naas_abi_sdk.discovery import DiscoveryConfiguration

module_type = research.ABIModule
assert list(module_type.get_workflow_classes()) == ["baz_workflow", "foo_workflow"]
assert list(module_type.get_pipeline_classes()) == ["foo_pipeline"]

client = MagicMock()
client.__aenter__ = AsyncMock(return_value=client)
client.__aexit__ = AsyncMock(return_value=False)
sdk_module.ABIClient = lambda *a, **k: client


class Session:
    # A registration that is READY at once: no broker, no discovery service.
    def __init__(self, client, descriptor, rollout_id="", rollout_modules=()):
        self.descriptor, self.rollout_id = descriptor, rollout_id
        self.instance_id, self.status, self.initialized = "i", "READY", False
        self.drain_requested, self.task = asyncio.Event(), None

    async def start(self):
        pass

    async def renew(self):
        pass

    async def close(self):
        pass


hosted = []


class JobHost:
    # Each workflow and pipeline is a durable workflow: a job of the module.
    def __init__(self, transport, documents, module_id, project, jobs, **kwargs):
        hosted.extend(sorted(jobs))

    async def start(self):
        pass

    async def drain(self, timeout):
        pass

    async def close(self):
        pass


sdk_module.DiscoverySession = Session
job_host.JobHost = JobHost


class Agent:
    # An agent takes its tools when it is built, in on_initialized.
    def __init__(self, tools):
        self.tools = {tool.name: tool for tool in tools}


agents = []


async def on_initialized(self):
    await self.build_processes()
    agents.append(
        Agent(
            [
                *self.get_workflow_instance("foo_workflow").as_tools(),
                *self.get_pipeline_instance("foo_pipeline").as_tools(),
            ]
        )
    )


async def run(self):
    tools = agents[0].tools
    answer = await tools["foo_workflow"].ainvoke({"message": "hi"})
    graph = await tools["foo_pipeline"].ainvoke({"iri": "urn:a", "label": "A"})
    return sorted(tools), answer, graph["format"], hosted


# Without discovery or the engine's models, the template's agent, app and job
# cannot be hosted: this run keeps what the test is about.
module_type.agents = ()
module_type.apps = ()
module_type.jobs = ()
module_type._decorated_jobs = {}
module_type.on_initialized = on_initialized
module_type.run = run
print(
    asyncio.run(
        sdk_module.run_module(
            module_type,
            url="nats://unused",
            token="t",
            discovery=DiscoveryConfiguration(),
        )
    )
)
"""
    built = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    assert (
        built.stdout.strip()
        == "(['foo_pipeline', 'foo_workflow'], {'message': 'hi'}, 'text/turtle', "
        "['pipeline.foo_pipeline', 'workflow.baz_workflow', 'workflow.foo_workflow'])"
    )


def test_core_scaffolds_still_work_in_an_in_engine_module(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "legacy", "--in-engine")
    workflows = root / "src" / "legacy" / "workflows"

    result = _invoke(_new_workflow, workflows, "Thing")

    assert result.exit_code == 0, result.output
    assert (workflows / "ThingWorkflow.py").is_file()
    assert _CORE_IMPORT.search((workflows / "ThingWorkflow.py").read_text())


def test_the_in_engine_pipeline_and_integration_stay_core_code(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _invoke(_new_module, root, "legacy", "--in-engine")
    package = root / "src" / "legacy"

    for kind, folder, cls in (
        ("pipeline", "pipelines", "ThingPipeline"),
        ("integration", "integrations", "ThingIntegration"),
    ):
        result = _scaffold(kind, package, folder)
        assert result.exit_code == 0, result.output
        code = (package / folder / f"{cls}.py").read_text()
        assert _CORE_IMPORT.search(code) and "naas_abi_sdk" not in code
        assert not (package / folder / f"{cls}_test.py").exists()


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
