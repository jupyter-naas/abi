# `module` (CLI group)

## What it is
A `click` command group that provides CLI subcommands for inspecting engine modules. Currently it exposes a `list` command that prints available modules and whether they are enabled.

## Public API
- **`module()`** (`click` group: `module`)
  - Root command group.
- **`list()`** (`click` command: `module list`)
  - Loads engine configuration via `EngineConfiguration.load_configuration()`.
  - Renders a Rich table titled **"Available Modules"** with columns:
    - `Module`
    - `Enabled`

## Configuration/Dependencies
- **Dependencies**
  - `click` (CLI framework)
  - `rich` (`Console`, `Table`) for formatted output
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration.EngineConfiguration`
- **Configuration source**
  - Uses `EngineConfiguration.load_configuration()`; module data is read from `configuration.modules`.

## Usage
Minimal integration into a `click` CLI app:

```python
import click
from naas_abi_cli.cli.module import module as module_group

@click.group()
def cli():
    pass

cli.add_command(module_group)

if __name__ == "__main__":
    cli()
```

Then run:

```bash
python app.py module list
```

## Caveats
- Assumes `EngineConfiguration.load_configuration()` succeeds and returns an object with a `modules` iterable where each item has `module` and `enabled` attributes.
