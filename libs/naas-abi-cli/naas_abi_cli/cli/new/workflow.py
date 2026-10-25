import os
from pathlib import Path

import click

import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .remote_module import ensure_package, is_remote_module, target_dir
from .utils import to_pascal_case, to_snake_case


@new.command("workflow")
@click.argument("workflow_name", required=True)
@click.argument("workflow_path", required=False, default=".")
def _new_workflow(workflow_name: str, workflow_path: str = "."):
    """Create a workflow: an SDK one inside a remote module, a naas_abi_core one
    inside an in-engine module."""
    remote = is_remote_module(target_dir(workflow_path))
    new_workflow(workflow_name, workflow_path, remote=remote)
    if remote:
        name = to_snake_case(to_pascal_case(workflow_name) + "Workflow")
        click.echo(
            f"Created {to_pascal_case(workflow_name)}Workflow.py (naas_abi_sdk). "
            f"The module builds it after on_initialized, as '{name}'; its agents call "
            f"it with self.get_workflow('{name}').as_tools(). It needs the "
            "naas-abi-sdk[workflows] extra (and [agents] for as_tools)."
        )


def new_workflow(
    workflow_name: str,
    workflow_path: str = ".",
    extra_values: dict | None = None,
    remote: bool = False,
):
    """``remote``: an SDK workflow for a remote module (no naas_abi_core)."""
    if extra_values is None:
        extra_values = {}
    workflow_name = to_pascal_case(workflow_name)

    if workflow_path == ".":
        workflow_path = os.getcwd()

    if not os.path.exists(workflow_path):
        os.makedirs(workflow_path, exist_ok=True)
    if remote:
        ensure_package(Path(workflow_path))

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__),
            "cli/new/templates/remote_workflow"
            if remote
            else "cli/new/templates/workflow",
        ),
        destination_path=workflow_path,
    )

    copier.copy(
        values={
            "workflow_name_pascal": to_pascal_case(workflow_name),
            "workflow_name_snake": to_snake_case(workflow_name),
            "workflow_name_upper": to_snake_case(workflow_name).upper(),
        }
        | extra_values
    )
