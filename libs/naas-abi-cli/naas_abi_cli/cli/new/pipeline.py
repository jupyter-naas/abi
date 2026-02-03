import os

import click
import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .utils import to_pascal_case


@new.command("pipeline")
@click.argument("pipeline_name", required=True)
@click.argument("pipeline_path", required=False, default=".")
def _new_pipeline(pipeline_name: str, pipeline_path: str = "."):
    new_pipeline(pipeline_name, pipeline_path)


def new_pipeline(pipeline_name: str, pipeline_path: str = ".", extra_values: dict = {}):
    pipeline_name = to_pascal_case(pipeline_name)

    if pipeline_path == ".":
        pipeline_path = os.getcwd()

    if not os.path.exists(pipeline_path):
        os.makedirs(pipeline_path, exist_ok=True)

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/pipeline"
        ),
        destination_path=pipeline_path,
    )

    copier.copy(
        values={"pipeline_name_pascal": to_pascal_case(pipeline_name)} | extra_values
    )
