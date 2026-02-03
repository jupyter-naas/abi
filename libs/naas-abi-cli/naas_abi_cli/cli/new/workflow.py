import os

import click
import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .utils import to_pascal_case


@new.command("workflow")
@click.argument("workflow_name", required=True)
@click.argument("workflow_path", required=False, default=".")
def _new_workflow(workflow_name: str, workflow_path: str = "."):
    new_workflow(workflow_name, workflow_path)


def new_workflow(workflow_name: str, workflow_path: str = ".", extra_values: dict = {}):
    workflow_name = to_pascal_case(workflow_name)

    if workflow_path == ".":
        workflow_path = os.getcwd()

    if not os.path.exists(workflow_path):
        os.makedirs(workflow_path, exist_ok=True)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/workflow"
        ),
        destination_path=workflow_path,
    )

    copier.copy(
        values={"workflow_name_pascal": to_pascal_case(workflow_name)} | extra_values
    )
