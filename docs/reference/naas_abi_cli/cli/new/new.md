# `new` (Click command group)

## What it is
- A `click` command group named **`new`** intended to act as a parent for subcommands in a CLI.

## Public API
- `new()`  
  - A Click **group** registered under the command name `"new"`.
  - Currently has no implementation (`pass`) and no subcommands defined in this module.

## Configuration/Dependencies
- **Dependencies**
  - `click` (used to define the CLI group via `@click.group`).

## Usage
Minimal example of integrating this group into a CLI:

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

Run (after installing your package/module so imports work):

```bash
python your_cli.py new
```

## Caveats
- No subcommands are defined in this module; invoking `new` alone will only show Click’s help/usage output unless subcommands are added elsewhere.
