import click
from rich.console import Console
from rich.table import Table

from naas_abi_core.engine.Engine import Engine


@click.group("agent")
def agent():
    pass


@agent.command("list")
def list():
    engine = Engine()
    engine.load()

    console = Console()
    table = Table(
        title="Available Agents", show_header=True, header_style="bold magenta"
    )
    table.add_column("Module", style="cyan", no_wrap=True)
    table.add_column("Agent", style="green")

    modules = engine.modules
    for module in modules:
        for agent in modules[module].agents:
            table.add_row(module, agent.__name__)

    console.print(table)
