# `init` (CLI command)

## What it is
A `click`-based CLI command named `init` that ensures a target directory exists, creating it if needed.

## Public API
- `init(path: str)`
  - Click command (`@click.command("init")`) with one required argument:
    - `path`: directory path to initialize.
  - Behavior:
    - If `path` is `"."`, it uses the current working directory (`os.getcwd()`).
    - Creates the directory at `path` if it does not exist (`os.makedirs(..., exist_ok=True)`).

## Configuration/Dependencies
- Standard library: `os`
- Third-party: `click`

## Usage
```python
import click
from naas_abi_cli.cli.init import init

# Example invocation via Click's testing runner:
from click.testing import CliRunner

runner = CliRunner()
result = runner.invoke(init, ["./my_project"])
assert result.exit_code == 0
```

## Caveats
- The command only creates directories; it does not initialize any project scaffolding (a commented-out `uv init` call is present but inactive).
- Errors from invalid paths/permissions will propagate from `os.makedirs`.
