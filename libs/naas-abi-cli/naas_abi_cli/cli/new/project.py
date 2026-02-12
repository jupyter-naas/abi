import os
import subprocess

import click
import naas_abi_cli
from naas_abi_cli.cli.deploy.local import setup_local_deploy
from naas_abi_cli.cli.utils.Copier import Copier

from .module import new_module
from .new import new
from .utils import to_kebab_case, to_pascal_case, to_snake_case


@new.command("project")
@click.argument("project-name", required=False, default=None)
@click.argument("project-path", required=False, default=None)
@click.option(
    "--with-local-deploy/--without-local-deploy",
    default=True,
    help="Generate local docker-compose and deployment scaffolding (default: enabled).",
)
def new_project(
    project_name: str | None,
    project_path: str | None,
    with_local_deploy: bool,
):
    project_name = to_kebab_case(project_name)
    # Defaults must be evaluated at runtime so they reflect the caller's CWD.
    if project_name is None:
        project_name = os.path.basename(os.getcwd())
    if project_path is None:
        project_path = os.getcwd()
    # Resolve relative segments (., ..) and user home (~) to a normalized absolute path.
    project_path = os.path.abspath(os.path.expanduser(project_path))

    # Ensure the last path component matches the project name, not just the suffix.
    if os.path.basename(os.path.normpath(project_path)) != project_name:
        project_path = os.path.join(project_path, project_name)

    if not os.path.exists(project_path):
        os.makedirs(project_path, exist_ok=True)
    elif len(os.listdir(project_path)) > 0:
        print(f"Folder {project_path} already exists and is not empty.")
        exit(1)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/project"
        ),
        destination_path=project_path,
    )
    copier.copy(
        values={
            "project_name": project_name,
            "project_name_snake": to_snake_case(project_name),
            "project_name_pascal": to_pascal_case(project_name),
        }
    )

    # Calling new_module to create the module in the src folder
    new_module(project_name, os.path.join(project_path, "src"), quiet=True)

    if with_local_deploy:
        setup_local_deploy(project_path)

    # Run dependency install without shell to avoid quoting issues on paths with spaces.
    subprocess.run(
        [
            "uv",
            "add",
            "naas-abi-core[all]",
            "naas-abi-marketplace[ai-chatgpt]",
            "naas-abi",
            "naas-abi-cli",
        ],
        cwd=project_path,
        check=True,
    )
