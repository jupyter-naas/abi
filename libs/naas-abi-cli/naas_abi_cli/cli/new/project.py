import os
import subprocess

import click

import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new


@new.command("project")
@click.argument("project-name", default=os.path.basename(os.getcwd()))
@click.argument("project-path", default=os.getcwd())
def new_project(project_name: str, project_path: str):
    # Resolve relative segments (., ..) and user home (~) to a normalized absolute path.
    project_path = os.path.abspath(os.path.expanduser(project_path))

    # Ensure the last path component matches the project name, not just the suffix.
    if os.path.basename(os.path.normpath(project_path)) != project_name:
        project_path = os.path.join(project_path, project_name)
    print(project_path)

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
            "project_name_snake": project_name.replace("-", "_"),
        }
    )

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
