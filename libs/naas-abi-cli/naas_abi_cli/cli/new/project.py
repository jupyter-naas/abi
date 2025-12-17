import os
import shutil
import subprocess

import click
import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new


@new.command("project")
@click.argument("project-name", default=os.path.basename(os.getcwd()))
@click.argument("project-path", default=os.getcwd())
@click.option("--force", is_flag=True, help="Overwrite existing folder")
def new_project(project_name: str, project_path: str, force: bool):
    # Resolve relative segments (., ..) and user home (~) to a normalized absolute path.
    project_path = os.path.abspath(os.path.expanduser(project_path))

    if not project_path.endswith(project_name):
        project_path = os.path.join(project_path, project_name)
    print(project_path)

    if not os.path.exists(project_path):
        os.makedirs(project_path, exist_ok=True)
    elif len(os.listdir(project_path)) > 0:
        if not force:
            print(f"Folder {project_path} already exists and is not empty.")
            response = click.confirm(
                "Do you want to continue and overwrite the existing folder? All content will be removed.",
                default=False,
                abort=True,
            )
            if not response:
                return
        shutil.rmtree(project_path)
        os.makedirs(project_path, exist_ok=True)

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
        ],
        cwd=project_path,
        check=True,
    )
