import os

import click
import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .utils import to_kebab_case, to_pascal_case, to_snake_case


@new.command("module")
@click.argument("module_name", required=True)
@click.argument("module_path", required=False, default=".")
def _new_module(module_name: str, module_path: str = "."):
    new_module(module_name, module_path)


def new_module(module_name: str, module_path: str = ".", quiet: bool = False):
    module_name = to_kebab_case(module_name)

    if module_path == ".":
        module_path = os.path.join(os.getcwd(), to_snake_case(module_name))
    else:
        module_path = os.path.join(module_path, to_snake_case(module_name))

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
            "module_name_snake": to_snake_case(module_name),
            "module_name_pascal": to_pascal_case(module_name),
        }
    )

    if not quiet:
        print(f"\nModule '{module_name}' has been created at:\n  {module_path}\n")
        print("To enable this module, add the following to your config.yaml:\n")
        print("modules:")
        print(f"  - path: {module_path}")
        print("    enabled: true\n")
