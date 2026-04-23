# `new_integration` (integration scaffold generator)

## What it is
- Implements the `naas-abi-cli new integration` command.
- Creates (if needed) a target directory and copies an “integration” template into it using a `Copier`.

## Public API
- `new_integration(integration_name: str, integration_path: str = ".", extra_values: dict = {})`
  - Normalizes `integration_name` to PascalCase.
  - Resolves `integration_path` (`"."` becomes current working directory).
  - Ensures the destination directory exists.
  - Copies templates from the package’s `cli/new/templates/integration` directory into the destination.
  - Passes template values:
    - `integration_name_pascal`: PascalCase integration name
    - plus any `extra_values` merged in.

- CLI command: `new integration`
  - Implemented by `_new_integration(integration_name, integration_path=".")`
  - Delegates to `new_integration(...)`.

## Configuration/Dependencies
- Depends on:
  - `click` (CLI arguments and command registration)
  - `naas_abi_cli` (used to locate the templates directory)
  - `naas_abi_cli.cli.utils.Copier.Copier` (template copying)
  - `.utils.to_pascal_case` (name normalization)
- Template source directory (computed at runtime):
  - `<naas_abi_cli package dir>/cli/new/templates/integration`

## Usage
### From Python
```python
from naas_abi_cli.cli.new.integration import new_integration

new_integration("my_integration", "./out_dir")
```

### From CLI
```bash
naas-abi-cli new integration my_integration .
```

## Caveats
- `extra_values` has a mutable default (`{}`); avoid relying on mutation across calls.
- `integration_name` is always converted to PascalCase; exact transformation depends on `to_pascal_case`.
