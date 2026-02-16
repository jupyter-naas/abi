import os

import click
import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .utils import to_pascal_case


@new.command("orchestration")
@click.argument("orchestration_name", required=True)
@click.argument("orchestration_path", required=False, default=".")
def _new_orchestration(orchestration_name: str, orchestration_path: str = "."):
    new_orchestration(orchestration_name, orchestration_path)


def new_orchestration(
    orchestration_name: str, orchestration_path: str = ".", extra_values: dict = {}
):
    orchestration_name = to_pascal_case(orchestration_name)

    if orchestration_path == ".":
        orchestration_path = os.getcwd()

    if not os.path.exists(orchestration_path):
        os.makedirs(orchestration_path, exist_ok=True)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/orchestration"
        ),
        destination_path=orchestration_path,
    )

    copier.copy(
        values={"orchestration_name_pascal": to_pascal_case(orchestration_name)}
        | extra_values
    )
