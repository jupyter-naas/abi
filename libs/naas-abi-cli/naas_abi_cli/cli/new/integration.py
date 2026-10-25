import os
from pathlib import Path

import click

import naas_abi_cli
from naas_abi_cli.cli.utils.Copier import Copier

from .new import new
from .remote_module import ensure_package, is_remote_module, target_dir
from .utils import to_pascal_case, to_snake_case


@new.command("integration")
@click.argument("integration_name", required=True)
@click.argument("integration_path", required=False, default=".")
def _new_integration(integration_name: str, integration_path: str = "."):
    """Create an integration: an SDK one inside a remote module, a naas_abi_core one
    inside an in-engine module."""
    remote = is_remote_module(target_dir(integration_path))
    new_integration(integration_name, integration_path, remote=remote)
    if remote:
        click.echo(
            f"Created {to_pascal_case(integration_name)}Integration.py (naas_abi_sdk). "
            "Nothing in the engine consumes it: build it in a workflow, pipeline or "
            "agent, with credentials from self.engine.services.secret (declare the "
            "secret service in ModuleDependencies)."
        )


def new_integration(
    integration_name: str,
    integration_path: str = ".",
    extra_values: dict | None = None,
    remote: bool = False,
):
    """``remote``: an SDK integration for a remote module (no naas_abi_core)."""
    if extra_values is None:
        extra_values = {}
    integration_name = to_pascal_case(integration_name)

    if integration_path == ".":
        integration_path = os.getcwd()

    if not os.path.exists(integration_path):
        os.makedirs(integration_path, exist_ok=True)
    if remote:
        ensure_package(Path(integration_path))

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__),
            "cli/new/templates/remote_integration"
            if remote
            else "cli/new/templates/integration",
        ),
        destination_path=integration_path,
    )

    copier.copy(
        values={
            "integration_name_pascal": to_pascal_case(integration_name),
            "integration_name_upper": to_snake_case(integration_name).upper(),
        }
        | extra_values
    )
