# `init` (naas_abi_cli.cli.init)

## What it is
A small Click CLI command that ensures a target directory exists. It resolves `"."` to the current working directory and creates the directory path if missing.

## Public API
- `init(path: str)`  
  - Click command named `init`.
  - Arguments:
    - `path`: target directory path; `"."` is treated as `os.getcwd()`.
  - Behavior:
    - Creates the directory (and parents) with `os.makedirs(..., exist_ok=True)`.

## Configuration/Dependencies
- Standard library: `os`
- Third-party: `click` (used to define the CLI command and argument parsing)

## Usage
### As a Click command (via a Click group/entrypoint)
```python
import click
from naas_abi_cli.cli.init import init

@click.group()
def cli():
    pass

cli.add_command(init)

if __name__ == "__main__":
    cli()
```

Run:
```bash
python your_cli.py init .
python your_cli.py init /tmp/my_project
```

## Caveats
- The command only creates directories; it does not initialize project files.
- A commented-out line suggests a future `uv init` step, but it is not executed.
