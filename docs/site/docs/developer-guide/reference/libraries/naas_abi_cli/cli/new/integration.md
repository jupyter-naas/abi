# `new_integration`

## What it is
- Integration scaffold generator used by the `naas-abi-cli new integration` command.
- Copies an “integration” template into a target directory using `Copier`.

## Public API
- `new_integration(integration_name: str, integration_path: str = ".", extra_values: dict | None = None)`
  - Converts `integration_name` to PascalCase.
  - Resolves `integration_path`:
    - `"."` becomes `os.getcwd()`.
    - Creates the directory if it does not exist.
  - Copies templates from the package template directory into `integration_path`.
  - Passes template values:
    - `integration_name_pascal`: PascalCase integration name
    - plus any `extra_values` merged in.

- CLI command function: `_new_integration(integration_name: str, integration_path: str = ".")`
  - Registered as `new integration` under the `new` click command group.
  - Calls `refuse_in_remote_module("integration", integration_path)` then delegates to `new_integration(...)`.

## Configuration/Dependencies
- Standard library: `os`
- External:
  - `click` (CLI registration/arguments)
  - `naas_abi_cli` (used to locate installed package path for templates)
- Internal:
  - `naas_abi_cli.cli.utils.Copier.Copier` (template copier)
  - `.utils.to_pascal_case` (name normalization)
  - `.remote_module.refuse_in_remote_module` (CLI guard)
- Template source directory (computed at runtime):
  - `<dir_of_naas_abi_cli_package>/cli/new/templates/integration`

## Usage

### From Python
```python
from naas_abi_cli.cli.new.integration import new_integration

new_integration("my_integration", "./out")
```

### From CLI
```bash
naas-abi-cli new integration my_integration .
```

## Caveats
- `integration_name` is always normalized to PascalCase (behavior depends on `to_pascal_case`).
- `new_integration()` creates `integration_path` if missing (including nested directories).
