import os
from pathlib import Path

import click
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from rich.console import Console
from rich.table import Table


@click.group("module")
def module():
    pass


@module.command("list")
def list() -> None:
    configuration: EngineConfiguration = EngineConfiguration.load_configuration()

    console = Console()
    table = Table(
        title="Available Modules", show_header=True, header_style="bold magenta"
    )
    table.add_column("Module", style="cyan", no_wrap=True)
    table.add_column("Enabled", style="green")

    for module in configuration.modules:
        table.add_row(module.module, str(module.enabled))

    console.print(table)


@module.command("key")
@click.argument("module_id")
def key(module_id: str) -> None:
    """Print the module key of MODULE_ID.

    A remote module signs its tokens with it (ABI_MODULE_KEY), and the engine
    accepts them for MODULE_ID only. It is derived from the project's
    NATS_JWT_SECRET ($NATS_JWT_SECRET, else ./.env), which the module never
    gets. A new secret means new keys.
    """
    from naas_abi_core.engine.nats_auth import module_key

    from naas_abi_cli.cli.admin_credentials import NATS_SECRET, _read, _value

    secret = os.environ.get(NATS_SECRET) or _value(_read(Path(".env")), NATS_SECRET)
    if not secret:
        raise click.ClickException(
            f"No {NATS_SECRET}: run this in the project (its .env) or set it."
        )
    try:
        click.echo(module_key(secret, module_id))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
