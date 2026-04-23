# `agent` (CLI command group)

## What it is
- A `click` command group that provides an `agent list` subcommand.
- It loads the Naas ABI `Engine`, reads available agents from loaded modules, and prints them as a table using `rich`.

## Public API
- `agent()`
  - Click command group registered under the name `agent`.
- `list()`
  - Click subcommand `agent list`.
  - Loads the engine and outputs a table of available agents grouped by module.

## Configuration/Dependencies
- **Dependencies**
  - `click` (CLI framework)
  - `naas_abi_core.engine.Engine.Engine` (`Engine` used to load modules/agents)
  - `rich` (`Console`, `Table` for formatted terminal output)
- **Runtime expectations**
  - `Engine().load()` populates `engine.modules` where:
    - Keys are module names (strings)
    - Values expose an `.agents` iterable of agent objects/classes with a `__name__` attribute

## Usage
Minimal example integrating this command group into a CLI:

```python
import click
from naas_abi_cli.cli.agent import agent

@click.group()
def cli():
    pass

cli.add_command(agent)

if __name__ == "__main__":
    cli()
```

Then run:

```bash
python app.py agent list
```

## Caveats
- The subcommand name is `list`, which shadows Python’s built-in `list` within this module.
- Output depends on `Engine.load()` successfully discovering modules and agents; if no modules/agents are loaded, the table will be empty.
