# `module` (CLI command group)

## What it is
A `click` command group that provides module-related CLI commands. Currently it supports listing configured modules from the Naas ABI engine configuration and renders them as a table using `rich`.

## Public API
- `module()`  
  - Click command group registered under the name `module`.
- `module list` (function `list() -> None`)  
  - Loads engine configuration via `EngineConfiguration.load_configuration()`.
  - Prints a table of available modules and whether they are enabled.

## Configuration/Dependencies
- **Dependencies**
  - `click` for CLI grouping/commands.
  - `rich` (`Console`, `Table`) for formatted terminal output.
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration.EngineConfiguration`
    - Must provide `load_configuration()` and expose `configuration.modules`.
    - Each module entry is expected to have `.module` and `.enabled` attributes.

## Usage
Minimal integration example (for a Click CLI entrypoint):

```python
import click
from naas_abi_cli.cli.module import module

@click.group()
def cli():
    pass

cli.add_command(module)

if __name__ == "__main__":
    cli()
```

Then run:

```bash
python your_cli.py module list
```

## Caveats
- The command assumes configuration can be loaded successfully and that `configuration.modules` is iterable with items exposing `module` and `enabled`. Errors from configuration loading are not handled in this module.
