import os

import click
import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .utils import to_pascal_case


@new.command("integration")
@click.argument("integration_name", required=True)
@click.argument("integration_path", required=False, default=".")
def _new_integration(integration_name: str, integration_path: str = "."):
    new_integration(integration_name, integration_path)


def new_integration(
    integration_name: str, integration_path: str = ".", extra_values: dict = {}
):
    integration_name = to_pascal_case(integration_name)

    if integration_path == ".":
        integration_path = os.getcwd()

    if not os.path.exists(integration_path):
        os.makedirs(integration_path, exist_ok=True)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/integration"
        ),
        destination_path=integration_path,
    )

    copier.copy(
        values={"integration_name_pascal": to_pascal_case(integration_name)}
        | extra_values
    )
