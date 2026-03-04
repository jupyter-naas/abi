# `agent` CLI group

## What it is
A `click` command group that exposes an `agent list` command to display available agents discovered/loaded by `naas_abi_core.engine.Engine`, formatted as a Rich table.

## Public API
- `agent()` *(click group: `agent`)*
  - Root command group for agent-related subcommands.
- `list()` *(click command: `agent list`)*
  - Loads the engine and prints a table of available agents grouped by module.
  - Sorting:
    - Modules are sorted alphabetically by module key.
    - Agents within each module are sorted alphabetically by `agent.__name__`.

## Configuration/Dependencies
- **Dependencies**
  - `click` for CLI definition.
  - `naas_abi_core.engine.Engine.Engine` for module/agent discovery (`Engine().load()`, `engine.modules`).
  - `rich` (`Console`, `Table`) for terminal output formatting.
- **Runtime expectations**
  - `Engine.load()` populates `engine.modules`.
  - Each `engine.modules[module]` exposes an `.agents` iterable of agent objects with a `__name__` attribute.

## Usage
This module is intended to be registered into a larger `click` CLI. Example of wiring it into an entrypoint:

```python
import click
from naas_abi_cli.cli.agent import agent as agent_group

@click.group()
def cli():
    pass

cli.add_command(agent_group)

if __name__ == "__main__":
    cli()
```

Then run:

```bash
python cli.py agent list
```

## Caveats
- The command name `list` shadows Python’s built-in `list` within this module’s scope.
- Output depends entirely on what `Engine.load()` discovers and how `engine.modules` / `.agents` are structured.
