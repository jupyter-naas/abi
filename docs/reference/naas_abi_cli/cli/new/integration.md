# `new_integration`

## What it is
- Implements the `naas-abi-cli new integration` command.
- Scaffolds a integration from a bundled template into a target path, for the kind of module it runs in: a `naas_abi_core` integration in an in-engine module, a `naas_abi_sdk` one in a remote module.

## Public API
- `new_integration(integration_name: str, integration_path: str = ".", extra_values: dict | None = None, remote: bool = False)`
  - Converts `integration_name` to PascalCase.
  - Resolves `integration_path` (`"."` becomes `os.getcwd()`) and creates the directory if it does not exist.
  - With `remote=True`, makes the folder a package (`ensure_package`): the scaffold's test imports the class relatively, and the module imports it by its dotted name.
  - Copies the templates, chosen by `remote`:
    - `remote=False` → `cli/new/templates/integration`
    - `remote=True` → `cli/new/templates/remote_integration` (imports `naas_abi_sdk` only, with a `<Name>Integration_test.py` beside it)
  - Template values: `integration_name_pascal` and `integration_name_upper`, merged with `extra_values` (dict union `|`).

- Click command: `naas-abi-cli new integration INTEGRATION_NAME [INTEGRATION_NAME_PATH]`
  - `_new_integration` detects the target with `is_remote_module(target_dir(integration_path))` and calls `new_integration(..., remote=remote)`.
  - In a remote module it prints what to do next: nothing in the engine consumes an integration: build it in a workflow, pipeline or agent, with credentials from `self.engine.services.secret` (declare the `secret` service).
  - It does not refuse in a remote module (only `abi new orchestration` does).

## Configuration/Dependencies
- **Python packages**
  - `click` (CLI command wiring)
  - `naas_abi_cli` (used to locate installed template files)
- **Internal utilities**
  - `Copier` from `naas_abi_cli.cli.utils.Copier` (copy/render step)
  - `to_pascal_case`, `to_snake_case` from `.utils`
  - `ensure_package`, `is_remote_module`, `target_dir` from `.remote_module`

## Usage

### CLI
```bash
naas-abi-cli new integration MyIntegration .
```

### Python
```python
from naas_abi_cli.cli.new.integration import new_integration

new_integration("my_integration", "./out")                 # naas_abi_core
new_integration("my_integration", "./out", remote=True)    # naas_abi_sdk
```

## Caveats
- If `integration_path == "."`, it is replaced with `os.getcwd()`.
- `integration_name` is converted to PascalCase; the template receives it under `integration_name_pascal`.
- The remote scaffold's methods are `async` and raise `IntegrationConnectionError` when the tool cannot be reached.
