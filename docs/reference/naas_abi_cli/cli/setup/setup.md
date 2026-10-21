# `setup` (CLI group)

## What it is
- A `click` command group named `setup` for the `naas_abi_cli` CLI.
- Acts as a namespace for subcommands that may be registered elsewhere.

## Public API
- `setup()`
  - Click command group entry point registered as `setup`.
  - Currently has no direct behavior (`pass`) and expects subcommands to be attached via Click.

## Configuration/Dependencies
- **Dependency:** `click`
- No configuration options or parameters are defined in this module.

## Usage
```python
import click
from naas_abi_cli.cli.setup.setup import setup

@setup.command("hello")
def hello():
    click.echo("hi")

if __name__ == "__main__":
    setup()
```

Run:
```bash
python your_script.py setup hello
```

## Caveats
- As defined here, `setup` has no subcommands; invoking it without additional registered commands will not perform any action.
