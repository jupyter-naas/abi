# `setup` (Click command group)

## What it is
- Defines a `click` command group named `setup` for use in a CLI application.

## Public API
- `setup()`
  - A `click` group registered under the command name `"setup"`.
  - Intended as a parent command for subcommands (none are defined in this file).

## Configuration/Dependencies
- **Dependency:** `click`

## Usage
```python
import click
from naas_abi_cli.cli.setup.setup import setup

@setup.command("hello")
def hello():
    click.echo("hello")

if __name__ == "__main__":
    setup()
```

Run:
```bash
python your_script.py setup hello
```

## Caveats
- This module only defines the group; it provides no subcommands by itself.
