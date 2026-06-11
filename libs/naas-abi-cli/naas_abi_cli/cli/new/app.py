import os

import click
import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .utils import to_kebab_case, to_pascal_case, to_snake_case


@new.command("app")
@click.argument("app_name", required=True)
@click.argument("app_path", required=False, default=".")
def _new_app(app_name: str, app_path: str = "."):
    new_app(app_name, app_path)


def new_app(app_name: str, app_path: str = ".", extra_values: dict = {}):
    """Scaffold an app folder (manifest.json + README.md + index.html).

    The app lives under ``<module>/apps/<app_name_snake>/`` and is discovered by
    the Nexus apps adapter from its ``manifest.json``. The HTML page is exposed
    via the ``html:index.html`` shorthand in the manifest's ``url`` field.
    """
    app_name = to_kebab_case(app_name)

    if app_path == ".":
        app_path = os.getcwd()

    if not os.path.exists(app_path):
        os.makedirs(app_path, exist_ok=True)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/apps"
        ),
        destination_path=app_path,
    )

    if "module_name_snake" not in extra_values:
        extra_values["module_name_snake"] = "your_module_name"

    copier.copy(
        values={
            "app_name": app_name,
            "app_name_snake": to_snake_case(app_name),
            "app_name_pascal": to_pascal_case(app_name),
            "app_title": app_name.replace("-", " ").title(),
        }
        | extra_values
    )
