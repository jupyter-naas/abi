"""`abi new module` for remote modules: SDK packages that run in their own process.

A remote module never imports ``naas_abi_core``. Inside a project it lands in
``src/<name>/``, gets a ``dev.modules`` entry in ``config.yaml`` (``abi dev up``
runs it) and a service in ``docker-compose.override.yml`` (``abi start`` runs
it). It is never added to ``modules:``: it registers itself through discovery.
``standalone`` instead creates a repository of its own, ready for ``git init``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import click
import jinja2
import yaml

import naas_abi_cli
from naas_abi_cli.cli.admin_credentials import (
    MissingNatsSecret,
    ensure_module_key,
    module_key_variable,
)
from naas_abi_cli.cli.utils.Copier import Copier

from .utils import to_pascal_case, to_snake_case

TEMPLATES = Path(naas_abi_cli.__file__).parent / "cli/new/templates"
COMPOSE_OVERRIDE = "docker-compose.override.yml"
ABI_GIT_URL = "https://github.com/jupyter-naas/abi.git"
# Standalone modules install naas-abi-proto and naas-abi-sdk from the ABI
# repository until both are on PyPI, pinned by default to the release tag of
# this CLI (semantic-release's tag_format), so they match the CLI that created
# the module and never move. `--abi-ref` picks another branch, tag or commit.
CLI_TAG_FORMAT = "naas-abi-cli-v{version}"


def default_abi_git_ref() -> str:
    """The release tag of the installed CLI: ``naas-abi-cli-v<version>``."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return CLI_TAG_FORMAT.format(version=version("naas-abi-cli"))
    except PackageNotFoundError as exc:
        raise click.ClickException(
            "Cannot tell which naas-abi-cli release this is; pass --abi-ref "
            "with the ABI tag or commit to install naas-abi-sdk from."
        ) from exc
# A dev module's name (EngineConfiguration_Dev.DevModuleConfiguration.name).
_DEV_MODULE_NAME = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
# What reading a project config can raise: the file, its Jinja, its YAML, or
# its validation (pydantic's ValidationError is a ValueError).
_CONFIG_ERRORS = (OSError, ValueError, jinja2.TemplateError, yaml.YAMLError)


@dataclass(frozen=True)
class Project:
    """The ABI project a module is created in."""

    root: Path

    @property
    def config(self) -> Path:
        return self.root / "config.yaml"

    @property
    def src(self) -> Path:
        return self.root / "src"

    def nats(self) -> bool:
        """Whether its Docker stack runs on NATS (``config.local.yaml`` first)."""
        from naas_abi_cli.cli.deploy.local import project_uses_nats

        return bool(project_uses_nats(str(self.root)))

    def nats_anywhere(self) -> bool:
        """Whether it runs on NATS natively or in Docker: either config has
        a ``nats:`` block."""
        from naas_abi_cli.cli.deploy.local import any_config_uses_nats

        return any_config_uses_nats(str(self.root))

    def discovery_project(self) -> str:
        """The configured discovery project, else the project's own name."""
        from naas_abi_cli.cli.dev_modules import configured_discovery_project

        try:
            configured = configured_discovery_project(self.config)
        except _CONFIG_ERRORS:  # an unreadable config falls back to the name
            configured = None
        return configured or to_snake_case(self.root.name) or "default"


def find_project(start: Path) -> Project | None:
    """The ABI project containing ``start``: the nearest folder with both
    ``config.yaml`` and ``pyproject.toml``."""
    for folder in (start, *start.parents):
        if (folder / "config.yaml").is_file() and (folder / "pyproject.toml").is_file():
            return Project(folder)
    return None


# Folders without __init__.py climbed to reach the enclosing package
# (apps/<name>/assets/ in a module).
_NON_PACKAGE_LEVELS = 3


def is_remote_module(path: Path) -> bool:
    """Whether ``path`` lies in a remote module: a package whose ``__init__.py``
    (it, or a parent package's) builds on ``naas_abi_sdk``."""
    folder = path
    while not folder.exists() and folder != folder.parent:
        folder = folder.parent
    for _ in range(_NON_PACKAGE_LEVELS):
        if (folder / "__init__.py").is_file() or folder == folder.parent:
            break
        folder = folder.parent
    while (folder / "__init__.py").is_file():
        if "naas_abi_sdk" in (folder / "__init__.py").read_text(encoding="utf-8"):
            return True
        folder = folder.parent
    return False


# What a remote module does instead of the in-engine scaffolds (naas_abi_core).
_REMOTE_ALTERNATIVES = {
    "workflow": "put the logic in a plain async function and call it from an "
    "agent tool or a @job on ABIModule",
    "pipeline": "put the logic in a plain async function, write through "
    "self.engine.services.triple_store, and run it from a @job on ABIModule",
    "integration": "call the third-party API from plain Python (httpx, "
    "requests) in the module, with its credentials from self.engine.services.secret",
    "orchestration": "declare a @job on ABIModule with Every/Cron/OnEvent "
    "triggers: remote modules schedule work on JetStream, not Dagster",
}


def target_dir(path: str) -> Path:
    return Path(os.getcwd()) if path == "." else Path(path).resolve()


def refuse_in_remote_module(scaffold: str, path: str) -> None:
    """``abi new <scaffold>`` writes naas_abi_core code, which a remote module
    must never import."""
    if is_remote_module(target_dir(path)):
        raise click.ClickException(
            f"{target_dir(path)} is in a remote module (naas_abi_sdk), and "
            f"`abi new {scaffold}` scaffolds naas_abi_core code it cannot "
            f"import. Instead, {_REMOTE_ALTERNATIVES[scaffold]}. Or create an "
            "in-engine module: `abi new module <name> --in-engine`."
        )


def template_values(
    module_name: str, module_id: str, discovery_project: str, **extra: str
) -> dict[str, str]:
    snake = to_snake_case(module_name)
    return {
        "module_name": module_name,
        "module_name_snake": snake,
        "module_name_pascal": to_pascal_case(module_name),
        "module_name_upper": snake.upper(),
        "module_id": module_id,
        "discovery_project": discovery_project,
        **extra,
    }


def render(template: str, destination: Path, values: dict[str, str]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    Copier(
        templates_path=str(TEMPLATES / template), destination_path=str(destination)
    ).copy(values=values)


def render_package(package: Path, values: dict[str, str]) -> None:
    """The package itself, its SDK agent and the app scaffold."""
    from .agent import new_agent
    from .app import new_app

    render("remote_module/package", package, values)
    new_agent(values["module_name"], str(package / "agents"), remote=True)
    new_app(
        values["module_name"],
        str(package / "apps"),
        extra_values={"module_name_snake": values["module_name_snake"]},
    )


# =============================================================================
# Project wiring: dev.modules and docker-compose.override.yml
# =============================================================================

_DEV_LINE = re.compile(r"^dev\s*:\s*(#.*)?$")
_MODULES_LINE = re.compile(r"^  modules\s*:\s*(#.*)?$")
_DEV_HEADER = """
# SDK modules `abi dev up` runs next to the engine, supervised (restarted when
# they exit on their own). The engine validates this block and otherwise
# ignores it. Logs: `abi dev logs <name>`; stop: `abi dev down --service <name>`.
dev:
"""


def _is_nested(line: str) -> bool:
    """Part of the enclosing block: indented, blank, or a comment."""
    return (
        line.startswith((" ", "\t"))
        or not line.strip()
        or line.lstrip().startswith("#")
    )


def _with_dev_module(text: str, entry: str) -> str | None:
    """``text`` with ``entry`` appended to ``dev.modules``; None when the
    block has a shape this edit does not handle (``modules: []``)."""
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    dev = next((i for i, line in enumerate(lines) if _DEV_LINE.match(line)), None)
    if dev is None:
        return "".join(lines) + _DEV_HEADER + "  modules:\n" + entry
    end = dev + 1
    while end < len(lines) and _is_nested(lines[end]):
        end += 1
    modules = next(
        (i for i in range(dev + 1, end) if _MODULES_LINE.match(lines[i])), None
    )
    if modules is None:
        if any(lines[i].startswith("  modules") for i in range(dev + 1, end)):
            return None
        return "".join(lines[: dev + 1] + ["  modules:\n", entry] + lines[dev + 1 :])
    # The list ends at the next key of `dev:` (two-space indent) or with the block.
    last = modules + 1
    while last < end and (
        lines[last].startswith("    ")
        or lines[last].startswith("  -")
        or not lines[last].strip()
    ):
        last += 1
    while last > modules + 1 and not lines[last - 1].strip():
        last -= 1
    return "".join(lines[:last] + [entry] + lines[last:])


def add_dev_module(config: Path, name: str, module: str, identity: str = "") -> bool:
    """Add ``name`` (``python -m module``, registering as ``identity``) to
    ``dev.modules`` in ``config``, keeping the file's comments and templating.
    False when it could not: the file is then left as it was."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
        load_dev_configuration,
    )

    original = config.read_text(encoding="utf-8")
    try:
        if name in {m.name for m in load_dev_configuration(str(config)).modules}:
            return True
    except _CONFIG_ERRORS:
        return False
    entry = f"    - name: {name}\n      module: {module}\n"
    if identity:
        entry += f"      identity: {identity}\n"
    updated = _with_dev_module(original, entry)
    if updated is None:
        return False
    config.write_text(updated, encoding="utf-8")
    try:
        added = name in {m.name for m in load_dev_configuration(str(config)).modules}
    except _CONFIG_ERRORS:
        added = False
    if not added:
        config.write_text(original, encoding="utf-8")
    return added


def compose_service(
    project: Project, name: str, package: Path, discovery_project: str, module_id: str
) -> dict:
    """The module's service: its SDK-only image, logged in to the stack's broker,
    signing as ``module_id`` with its module key (from ``.env``)."""
    context = "./" + package.relative_to(project.root).as_posix()
    variable = module_key_variable(name)
    return {
        "build": {
            "context": context,
            "additional_contexts": {
                "abi_proto": "./.abi/libs/naas-abi-proto",
                "abi_sdk": "./.abi/libs/naas-abi-sdk",
            },
        },
        "restart": "unless-stopped",
        "environment": [
            "ABI_NATS_URL=nats://module:${NATS_MODULE_PASSWORD}@nats:4222",
            # Its own key, never the project's NATS_JWT_SECRET.
            (
                f"ABI_MODULE_KEY=${{{variable}:?{variable} is not in .env: "
                f"abi module key {module_id}}}"
            ),
            f"ABI_DISCOVERY_PROJECT={discovery_project}",
            "LOG_LEVEL=${LOG_LEVEL:-INFO}",
        ],
        # Its first calls need the engine's model registry and documents.
        "depends_on": {"abi": {"condition": "service_healthy"}},
        "networks": ["abi-network"],
    }


_OVERRIDE_HEADER = """\
# Remote modules (`abi new module`), each in its own container, next to the
# stack in docker-compose.yml. Compose merges this file in (`abi start`,
# `abi deploy local-up`); `abi deploy local --regenerate` never rewrites it.
"""


def add_compose_service(project: Project, name: str, service: dict) -> bool:
    """Add ``service`` to the project's override file; False if one by that
    name exists already."""
    path = project.root / COMPOSE_OVERRIDE
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    document = (yaml.safe_load(existing) if existing else None) or {}
    services = document.get("services") or {}
    if name in services:
        return False
    services[name] = service
    document["services"] = services
    body = yaml.safe_dump(document, sort_keys=False, default_flow_style=False)
    # Rewriting an existing file drops its comments: keep the header at least.
    path.write_text(_OVERRIDE_HEADER + body, encoding="utf-8")
    return True


def compose_snippet(name: str, service: dict) -> str:
    return yaml.safe_dump({"services": {name: service}}, sort_keys=False)


# =============================================================================
# The command's two shapes
# =============================================================================


def create_in_project(project: Project, module_name: str, package: Path) -> None:
    """``src/<name>/`` in ``project``, wired into ``abi dev up`` and Compose."""
    name = module_name
    if not _DEV_MODULE_NAME.match(name):
        raise click.BadParameter(
            f"{name!r}: a module name starts with a letter and holds lowercase "
            "letters, digits and dashes (at most 63)."
        )
    try:
        dotted = ".".join(package.relative_to(project.src).parts)
    except ValueError as exc:
        raise click.BadParameter(
            f"{package} is outside {project.src}: `abi dev up` runs modules "
            "from the project's src/ folder."
        ) from exc
    discovery_project = project.discovery_project()
    module_id = f"{to_snake_case(project.root.name)}.{to_snake_case(name)}"
    render_package(package, template_values(name, module_id, discovery_project))
    render(
        "remote_module/in_project",
        package,
        template_values(name, module_id, discovery_project),
    )

    click.echo(f"\nRemote module '{name}' created at:\n  {package}\n")
    click.echo(
        "It runs in its own process and registers itself in discovery "
        f"(project {discovery_project!r}), so it is not added to `modules:`."
    )
    if add_dev_module(project.config, name, dotted, module_id):
        click.echo(
            f"- `abi dev up` runs it: added to dev.modules in {project.config.name}."
        )
    else:
        click.echo(
            f"- Could not edit dev.modules in {project.config.name}; add this "
            "for `abi dev up` to run it:\n\n"
            f"dev:\n  modules:\n    - name: {name}\n      module: {dotted}\n"
            f"      identity: {module_id}\n"
        )

    service = compose_service(project, name, package, discovery_project, module_id)
    if project.nats():
        # The service signs with its own key, kept in .env next to the secret.
        variable = module_key_variable(name)
        try:
            _, replaced = ensure_module_key(project.root / ".env", name, module_id)
        except MissingNatsSecret:
            click.echo(
                f"- No NATS_JWT_SECRET in .env to derive its key from. Once the "
                f"project has its secret (`abi deploy local`), add it: "
                f"echo {variable}=$(abi module key {module_id}) >> .env"
            )
        else:
            click.echo(
                f"- Its module key is in .env ({variable}): it signs its tokens as "
                f"{module_id} only."
            )
            if replaced:
                click.echo(
                    f"  Warning: {variable} in .env was another key (an older "
                    "NATS_JWT_SECRET?); replaced with the current secret's."
                )
    if not project.nats():
        click.echo(
            "- This project's Docker config has no `nats:` block, so its Docker "
            "stack has no broker for the module. See docs/migrate-to-nats.md; then add "
            f"this service to {COMPOSE_OVERRIDE}:\n\n" + compose_snippet(name, service)
        )
    elif not (project.root / "docker-compose.yml").exists():
        click.echo(
            "- No docker-compose.yml here (`abi deploy local` creates it). Its "
            f"service for {COMPOSE_OVERRIDE}:\n\n" + compose_snippet(name, service)
        )
    elif add_compose_service(project, name, service):
        click.echo(
            f"- `abi start` runs it: added the '{name}' service to {COMPOSE_OVERRIDE}."
        )
    else:
        click.echo(f"- {COMPOSE_OVERRIDE} already has a '{name}' service; left as is.")
    click.echo(
        "\nIts agent appears in Nexus once the module logs READY. "
        f"Logs: `abi dev logs {name}`.\n"
    )


def create_standalone(module_name: str, repository: Path, abi_git_ref: str) -> None:
    """A repository for one module: package under ``src/``, pyproject, Dockerfile."""
    snake = to_snake_case(module_name)
    values = template_values(
        module_name,
        snake,
        "default",
        abi_git_url=ABI_GIT_URL,
        abi_git_ref=abi_git_ref,
    )
    render("remote_module/standalone", repository, values)
    render_package(repository / "src" / snake, values)

    click.echo(
        f"\nStandalone remote module '{module_name}' created at:\n  {repository}\n"
    )
    click.echo("Next steps:")
    click.echo(f"  cd {repository}")
    click.echo("  git init && uv sync && uv run pytest")
    click.echo(
        f"  ABI_NATS_URL=... ABI_MODULE_KEY=$(abi module key {snake}) "
        f"ABI_DISCOVERY_PROJECT=... uv run python -m {snake}   # see README.md\n"
    )


def default_package_dir(project: Project | None, module_path: str, snake: str) -> Path:
    """Where ``abi new module <name> [path]`` puts the package."""
    if module_path == "." and project is not None:
        return project.src / snake
    base = Path(os.getcwd()) if module_path == "." else Path(module_path).resolve()
    return base / snake
