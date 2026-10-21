# `module` (CLI command group)

## What it is
A `click` command group providing module-related CLI commands:
- List configured modules from the Naas ABI engine configuration.
- Derive/print a module-specific signing key from the project NATS JWT secret.

## Public API
- `module` (click group)
  - Root command group registered as `module`.

- `module list` (`list() -> None`)
  - Loads engine configuration via `EngineConfiguration.load_configuration()`.
  - Renders a table (`rich`) of available modules and whether they are enabled.
  - Uses `configuration.modules`, expecting each item to expose:
    - `module` (identifier/name)
    - `enabled` (boolean)

- `module key MODULE_ID` (`key(module_id: str) -> None`)
  - Prints the derived module key for `MODULE_ID`.
  - Reads the NATS JWT secret from:
    - environment variable `NATS_JWT_SECRET` (via `naas_abi_cli.cli.admin_credentials.NATS_SECRET`), or
    - `./.env` (parsed via internal helpers in `naas_abi_cli.cli.admin_credentials`)
  - Calls `naas_abi_core.engine.nats_auth.module_key(secret, module_id)` and prints the result.
  - Raises `click.ClickException` if the secret is missing or the key derivation fails (`ValueError`).

## Configuration/Dependencies
- **Dependencies**
  - `click` for CLI commands and exceptions.
  - `rich` (`Console`, `Table`) for formatted output in `module list`.
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration.EngineConfiguration`
    - Must provide `load_configuration()` and a `modules` iterable.
  - `naas_abi_core.engine.nats_auth.module_key` for key derivation.
  - `naas_abi_cli.cli.admin_credentials` for:
    - `NATS_SECRET` constant (name of env var)
    - `_read` and `_value` helpers to read `./.env`

- **Environment / files**
  - `NATS_JWT_SECRET` (preferred) or `./.env` containing it, required for `module key`.

## Usage
Minimal integration example (registering the group in a Click app):

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

Example commands:

```bash
python your_cli.py module list
python your_cli.py module key my_module_id
```

## Caveats
- `module list` does not handle configuration-load failures; exceptions will propagate.
- `module key` must be run with access to `NATS_JWT_SECRET` (env var or `./.env` in the current working directory); otherwise it fails with `ClickException`.
- If `module_key()` raises `ValueError`, it is converted to a `ClickException` with the same message.
