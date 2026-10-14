import os
import sys
from pathlib import Path
from typing import Literal

import click

import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .agent import new_agent
from .app import new_app
from .integration import new_integration
from .new import new
from .orchestration import new_orchestration
from .pipeline import new_pipeline
from .remote_module import (
    create_in_project,
    create_standalone,
    default_abi_git_ref,
    default_package_dir,
    find_project,
)
from .utils import to_kebab_case, to_pascal_case, to_snake_case
from .workflow import new_workflow

ModuleKind = Literal["remote", "in-engine"]


@new.command("module")
@click.argument("module_name", required=True)
@click.argument("module_path", required=False, default=".")
@click.option(
    "--in-engine",
    "--local",
    "in_engine",
    is_flag=True,
    default=False,
    help=(
        "Create a classic module the engine loads (naas_abi_core: agents, "
        "integrations, pipelines, workflows, ontologies). Add it under "
        "`modules:` in config.yaml."
    ),
)
@click.option(
    "--standalone",
    is_flag=True,
    default=False,
    help=(
        "Create a remote module as a repository of its own (pyproject.toml, "
        "Dockerfile, README), for a team that ships it separately. The "
        "default outside an ABI project."
    ),
)
@click.option(
    "--abi-ref",
    default=None,
    help=(
        "With --standalone: the ABI branch, tag or commit naas-abi-sdk and "
        "naas-abi-proto install from (they are not on PyPI yet). Default: this "
        "CLI's release tag, naas-abi-cli-v<version>."
    ),
)
def _new_module(
    module_name: str,
    module_path: str = ".",
    in_engine: bool = False,
    standalone: bool = False,
    abi_ref: str | None = None,
):
    """Create a module. By default a remote module: it runs in its own process
    and reaches the engine only through NATS, with naas-abi-sdk.

    Inside a project it goes to src/<name>/, and `abi dev up` and `abi start`
    run it (dev.modules, docker-compose.override.yml). It registers itself
    through discovery, so it is not added to `modules:`.
    """
    if in_engine and standalone:
        raise click.UsageError(
            "--standalone creates a remote module: drop --in-engine."
        )
    new_module(
        module_name,
        module_path,
        kind="in-engine" if in_engine else "remote",
        standalone=standalone,
        abi_ref=abi_ref,
    )


def _empty_destination(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    elif len(os.listdir(path)) > 0:
        print(f"Folder {path} already exists and is not empty.")
        sys.exit(1)


def new_module(
    module_name: str,
    module_path: str = ".",
    quiet: bool = False,
    kind: ModuleKind = "remote",
    standalone: bool = False,
    abi_ref: str | None = None,
):
    """``kind="remote"``: an SDK module, in the enclosing project's ``src/``
    or, outside a project or with ``standalone``, as a repository of its own.
    ``kind="in-engine"``: the classic module the engine loads."""
    module_name = to_kebab_case(module_name)
    project = find_project(Path(os.getcwd()))

    if kind == "remote":
        if standalone or project is None:
            if not standalone:
                click.echo(
                    "Not inside an ABI project (no config.yaml + pyproject.toml): "
                    "creating a standalone module repository."
                )
            base = os.getcwd() if module_path == "." else module_path
            repository = Path(base).resolve() / module_name
            _empty_destination(str(repository))
            create_standalone(module_name, repository, abi_ref or default_abi_git_ref())
        else:
            package = default_package_dir(
                project, module_path, to_snake_case(module_name)
            )
            _empty_destination(str(package))
            create_in_project(project, module_name, package)
        return

    in_project = project is not None and module_path == "."
    module_path = str(
        default_package_dir(project, module_path, to_snake_case(module_name))
    )
    _empty_destination(module_path)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/module"
        ),
        destination_path=module_path,
    )

    copier.copy(
        values={
            "module_name": module_name,
            "module_name_snake": to_snake_case(module_name),
            "module_name_pascal": to_pascal_case(module_name),
        }
    )

    new_agent(
        module_name,
        os.path.join(module_path, "agents"),
        extra_values={"module_name_snake": to_snake_case(module_name)},
    )

    new_integration(
        module_name,
        os.path.join(module_path, "integrations"),
        extra_values={"module_name_snake": to_snake_case(module_name)},
    )

    new_pipeline(
        module_name,
        os.path.join(module_path, "pipelines"),
        extra_values={"module_name_snake": to_snake_case(module_name)},
    )

    new_workflow(
        module_name,
        os.path.join(module_path, "workflows"),
        extra_values={"module_name_snake": to_snake_case(module_name)},
    )

    new_orchestration(
        module_name,
        os.path.join(module_path, "orchestrations"),
        extra_values={"module_name_snake": to_snake_case(module_name)},
    )

    new_app(
        module_name,
        os.path.join(module_path, "apps"),
        extra_values={"module_name_snake": to_snake_case(module_name)},
    )

    if not quiet:
        # Configuration file requires an importable module namespace rather than an
        # actual file path on the filesystem, so the path is made relative to the
        # current working directory (the project's src/ in a project) and its
        # separators replaced with '.'
        root = str(project.src) if in_project and project is not None else os.getcwd()
        module_namespace = os.path.relpath(module_path, root).replace(os.sep, ".")

        print(f"\nModule '{module_name}' has been created at:\n  {module_path}\n")
        print("To enable this module, add the following to your config.yaml:\n")
        print("modules:")
        print(f"  - module: {module_namespace}")
        print("    enabled: true\n")
        print(
            "Note: please check the module import namespace root level that might need "
            "to be updated depending on your actual project structure.\n"
        )
