# `new` (Click command group)

## What it is
- A `click` command group named **`new`** intended to serve as a parent command for subcommands in a CLI.

## Public API
- `new()`  
  - A Click **group** registered under the command name `"new"`.
  - Currently contains no implementation and no subcommands in this module.

## Configuration/Dependencies
- Depends on:
  - `click` (for CLI command/group definition)

## Usage
Minimal runnable example wiring this group into a CLI:

```python
import click
from naas_abi_cli.cli.new.new import new

@click.group()
def cli():
    pass

cli.add_command(new)

if __name__ == "__main__":
    cli()
```

Run:

```bash
python app.py new
```

## Caveats
- The `new` group does nothing by itself (`pass`) and provides no subcommands in this file.
