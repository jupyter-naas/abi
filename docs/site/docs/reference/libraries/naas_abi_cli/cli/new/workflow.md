# `new_workflow` (workflow generator)

## What it is
- Implements the `naas-abi-cli new workflow` command.
- Copies a workflow template directory into a target path, injecting a PascalCase workflow name into template values.

## Public API
- `new_workflow(workflow_name: str, workflow_path: str = ".", extra_values: dict = {})`
  - Normalizes `workflow_name` to PascalCase.
  - Resolves `workflow_path`:
    - `"."` becomes `os.getcwd()`
    - Creates the directory if it does not exist
  - Uses `Copier` to copy templates from the package template folder to `workflow_path`.
  - Passes template values:
    - `workflow_name_pascal` (PascalCase string)
    - merged with `extra_values` (using dict union `|`)

- CLI entrypoint (Click command)
  - `naas-abi-cli new workflow WORKFLOW_NAME [WORKFLOW_PATH]`
  - Implemented by `_new_workflow(...)`, which delegates to `new_workflow(...)`.

## Configuration/Dependencies
- **Python packages**
  - `click` (CLI wiring)
  - `naas_abi_cli` (used to locate installed template files)
- **Internal utilities**
  - `Copier` from `naas_abi_cli.cli.utils.Copier` (performs template copy)
  - `to_pascal_case` from `.utils` (name normalization)
- **Template location**
  - `<naas_abi_cli package>/cli/new/templates/workflow`

## Usage
### From CLI
```bash
naas-abi-cli new workflow MyWorkflow .
```

### From Python
```python
from naas_abi_cli.cli.new.workflow import new_workflow

new_workflow("my_workflow", "./out")
```

## Caveats
- `extra_values` has a mutable default (`{}`); avoid mutating it inside callers. Prefer passing an explicit dict if needed.
- Requires Python support for dict union (`values | extra_values`), i.e., Python 3.9+.
