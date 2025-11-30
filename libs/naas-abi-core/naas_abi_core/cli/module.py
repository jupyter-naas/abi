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
