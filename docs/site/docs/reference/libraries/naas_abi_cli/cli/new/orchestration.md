# `orchestration`

## What it is
Creates a (legacy) Dagster orchestration scaffold by copying a bundled template directory into a target path, parameterized with an orchestration name.

## Public API
- `new_orchestration(orchestration_name: str, orchestration_path: str = ".", extra_values: dict | None = None)`
  - Converts `orchestration_name` to PascalCase.
  - Resolves `orchestration_path` (`"."` becomes the current working directory).
  - Creates the destination directory if missing.
  - Copies templates from `cli/new/templates/orchestration` into the destination using `Copier`, injecting template values.
- CLI command: `new orchestration ORCHESTRATION_NAME [ORCHESTRATION_PATH]`
  - Implemented by `_new_orchestration(...)`.
  - Calls `refuse_in_remote_module("orchestration", orchestration_path)` then `new_orchestration(...)`.

## Configuration/Dependencies
- Dependencies:
  - `click` for CLI binding.
  - `naas_abi_cli` to locate templates relative to the installed package.
  - `Copier` (`naas_abi_cli.cli.utils.Copier.Copier`) to render/copy template files.
  - `to_pascal_case` (`naas_abi_cli.cli.new.utils`) to normalize the orchestration name.
  - `refuse_in_remote_module` guard (`naas_abi_cli.cli.new.remote_module`).
- Template source directory (resolved at runtime):
  - `<naas_abi_cli package dir>/cli/new/templates/orchestration`
- Values passed to templates:
  - `orchestration_name_pascal`: PascalCase orchestration name.
  - Any key/values from `extra_values` are merged in.

## Usage

### CLI
```bash
naas-abi-cli new orchestration MyOrchestration ./out
```

### Python
```python
from naas_abi_cli.cli.new.orchestration import new_orchestration

new_orchestration("my orchestration", "./out", extra_values={"foo": "bar"})
```

## Caveats
- Marked as legacy in the CLI help text (“to be removed in the next major”).
- Requires `naas-abi-core[dagster]` per the CLI docstring.
- If `orchestration_path` is `"."`, the destination is `os.getcwd()`.
