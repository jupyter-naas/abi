# `new_workflow`

## What it is
- Implements the `naas-abi-cli new workflow` command.
- Generates a workflow scaffold by copying a bundled template directory into a target path, injecting a PascalCase workflow name into template values.

## Public API
- `new_workflow(workflow_name: str, workflow_path: str = ".", extra_values: dict | None = None)`
  - Converts `workflow_name` to PascalCase.
  - Resolves `workflow_path`:
    - `"."` becomes `os.getcwd()`
    - Creates the directory if it does not exist
  - Copies templates from the installed package templates folder into `workflow_path`.
  - Template values passed to the copier:
    - `workflow_name_pascal`: PascalCase workflow name
    - merged with `extra_values` via dict union (`|`)

- Click command: `naas-abi-cli new workflow`
  - `_new_workflow(workflow_name, workflow_path=".")`
    - Calls `refuse_in_remote_module("workflow", workflow_path)`
    - Delegates to `new_workflow(...)`

## Configuration/Dependencies
- **Python packages**
  - `click` (CLI command wiring)
  - `naas_abi_cli` (used to locate installed template files)
- **Internal utilities**
  - `Copier` from `naas_abi_cli.cli.utils.Copier` (performs the copy/render step)
  - `to_pascal_case` from `.utils` (workflow name normalization)
  - `refuse_in_remote_module` from `.remote_module` (CLI guard)
- **Template location**
  - `<naas_abi_cli package>/cli/new/templates/workflow`

## Usage

### CLI
```bash
naas-abi-cli new workflow MyWorkflow .
```

### Python
```python
from naas_abi_cli.cli.new.workflow import new_workflow

new_workflow("my_workflow", "./out")
```

## Caveats
- Requires Python 3.9+ due to dict union usage (`dict1 | dict2`).
- `workflow_name` is converted to PascalCase; the template receives the PascalCase value under `workflow_name_pascal`.
