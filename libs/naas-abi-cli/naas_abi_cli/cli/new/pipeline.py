import os
from pathlib import Path

import click

import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .remote_module import (
    component_destination,
    ensure_package,
    is_remote_module,
    target_dir,
)
from .utils import to_pascal_case, to_snake_case


@new.command("pipeline")
@click.argument("pipeline_name", required=True)
@click.argument("pipeline_path", required=False, default=".")
def _new_pipeline(pipeline_name: str, pipeline_path: str = "."):
    """Create a pipeline: an SDK one inside a remote module, a naas_abi_core one
    inside an in-engine module."""
    remote = is_remote_module(target_dir(pipeline_path))
    found = False
    if remote:
        pipeline_path, found = component_destination(
            pipeline_path, "pipelines", "pipeline"
        )
    new_pipeline(pipeline_name, pipeline_path, remote=remote)
    if remote and found:
        name = to_snake_case(to_pascal_case(pipeline_name) + "Pipeline")
        click.echo(
            f"Created {to_pascal_case(pipeline_name)}Pipeline.py (naas_abi_sdk). "
            f"The module builds it after on_initialized, as '{name}'. An agent created in "
            f"on_initialized needs `await self.build_processes()` first, then "
            f"self.get_pipeline('{name}').as_tools() (pass them as `tools=` to "
            "create_agent). It needs the naas-abi-sdk[workflows,rdf] extras (and [agents] "
            "for as_tools)."
        )
    elif remote:
        click.echo(
            f"Created {to_pascal_case(pipeline_name)}Pipeline.py in {pipeline_path} "
            "(naas_abi_sdk), outside the folder the module builds from."
        )


def new_pipeline(
    pipeline_name: str,
    pipeline_path: str = ".",
    extra_values: dict | None = None,
    remote: bool = False,
):
    """``remote``: an SDK pipeline for a remote module (no naas_abi_core)."""
    if extra_values is None:
        extra_values = {}
    pipeline_name = to_pascal_case(pipeline_name)

    if pipeline_path == ".":
        pipeline_path = os.getcwd()

    if not os.path.exists(pipeline_path):
        os.makedirs(pipeline_path, exist_ok=True)
    if remote:
        ensure_package(Path(pipeline_path))

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__),
            "cli/new/templates/remote_pipeline"
            if remote
            else "cli/new/templates/pipeline",
        ),
        destination_path=pipeline_path,
    )

    copier.copy(
        values={
            "pipeline_name_pascal": to_pascal_case(pipeline_name),
            "pipeline_name_snake": to_snake_case(pipeline_name),
            "pipeline_name_upper": to_snake_case(pipeline_name).upper(),
        }
        | extra_values
    )
