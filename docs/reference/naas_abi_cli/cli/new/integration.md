# `integration` (new integration scaffolding)

## What it is
Creates a new integration scaffold by copying a template directory into a target path, filling template variables (notably the integration name in PascalCase).

## Public API
- `new_integration(integration_name: str, integration_path: str = ".", extra_values: dict = {})`
  - Converts `integration_name` to PascalCase.
  - Resolves `integration_path` (`"."` becomes current working directory).
  - Ensures the destination directory exists.
  - Copies templates from the package’s `cli/new/templates/integration` directory into `integration_path`.
  - Passes template values including:
    - `integration_name_pascal`: PascalCase version of the integration name
    - Any additional `extra_values` merged in.

- CLI command: `new integration`
  - Registered as `@new.command("integration")`
  - Arguments:
    - `integration_name` (required)
    - `integration_path` (optional, default `"."`)
  - Invokes `new_integration(integration_name, integration_path)`.

## Configuration/Dependencies
- Depends on:
  - `click` for CLI argument parsing.
  - `naas_abi_cli` package location to find templates.
  - `naas_abi_cli.cli.utils.Copier.Copier` for template copying.
  - `.utils.to_pascal_case` for name normalization.
- Templates source directory (resolved at runtime):
  - `<naas_abi_cli package>/cli/new/templates/integration`

## Usage

### As a CLI command
```bash
naas-abi new integration MyIntegration .
```

### As a Python function
```python
from naas_abi_cli.cli.new.integration import new_integration

new_integration("my_integration", "./out")
```

## Caveats
- `extra_values` has a mutable default (`{}`); avoid mutating it across calls (pass a new dict if needed).
- `integration_name` is always converted to PascalCase; original casing is not preserved.
