import click
from naas_abi_core.engine.Engine import Engine
from rich.console import Console
from rich.table import Table


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

    # Sort modules alphabetically
    sorted_modules = sorted(modules.keys())

    for module in sorted_modules:
        # Sort agents alphabetically by name
        sorted_agents = sorted(modules[module].agents, key=lambda agent: agent.__name__)
        for agent in sorted_agents:
            table.add_row(module, agent.__name__)

    console.print(table)
