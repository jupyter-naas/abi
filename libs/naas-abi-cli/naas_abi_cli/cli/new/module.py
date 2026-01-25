import os

import click
import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new


def sanitize_module_name(module_name: str) -> str:
    return module_name.replace("-", "_").replace(" ", "_").lower()


@new.command("module")
@click.argument("module_name", required=True)
@click.argument("module_path", required=False, default=".")
def _new_module(module_name: str, module_path: str = "."):
    new_module(module_name, module_path)


def new_module(module_name: str, module_path: str = "."):
    module_name = sanitize_module_name(module_name)

    if module_path == ".":
        module_path = os.path.join(os.getcwd(), module_name)
    else:
        module_path = os.path.join(module_path, module_name)

    if not os.path.exists(module_path):
        os.makedirs(module_path, exist_ok=True)
    elif len(os.listdir(module_path)) > 0:
        print(f"Folder {module_path} already exists and is not empty.")
        exit(1)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/module"
        ),
        destination_path=module_path,
    )

    copier.copy(
        values={
            "module_name": module_name,
            "module_name_snake": module_name.replace("-", "_"),
            "module_name_pascal": module_name.replace("-", "").capitalize(),
        }
    )
