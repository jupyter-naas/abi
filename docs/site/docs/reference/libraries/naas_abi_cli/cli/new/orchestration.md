# `orchestration` (new orchestration generator)

## What it is
Creates a new orchestration scaffold by copying a bundled template directory into a target path, parameterized with an orchestration name.

## Public API
- `new_orchestration(orchestration_name: str, orchestration_path: str = ".", extra_values: dict = {})`
  - Normalizes `orchestration_name` to PascalCase.
  - Resolves `orchestration_path` (`"."` becomes current working directory).
  - Ensures the destination directory exists.
  - Copies orchestration templates into the destination using `Copier`, injecting template values.
- CLI command: `new orchestration ORCHESTRATION_NAME [ORCHESTRATION_PATH]`
  - Implemented by `_new_orchestration(...)` and calls `new_orchestration(...)`.

## Configuration/Dependencies
- Depends on:
  - `click` for CLI wiring.
  - `naas_abi_cli` package location to resolve the template folder:
    - `<naas_abi_cli package>/cli/new/templates/orchestration`
  - `Copier` (`naas_abi_cli.cli.utils.Copier.Copier`) to perform template copying.
  - `to_pascal_case` (`.utils`) to normalize names.
- Template values passed to `Copier.copy(...)`:
  - `orchestration_name_pascal`: PascalCase version of the provided name.
  - Any additional keys from `extra_values` are merged in.

## Usage
### As a CLI command
```bash
naas-abi-cli new orchestration MyOrchestration ./out
```

### As a Python function
```python
from naas_abi_cli.cli.new.orchestration import new_orchestration

new_orchestration("my orchestration", "./out", extra_values={"foo": "bar"})
```

## Caveats
- `extra_values` has a mutable default (`{}`); passing your own dict is recommended when adding values.
- If `orchestration_path` is `"."`, it uses `os.getcwd()` as the destination.
