# `new_workflow` (workflow generator)

## What it is
Creates a new workflow scaffold from a bundled template and writes it to a target directory. Exposed both as a Click subcommand (`new workflow`) and as a Python function.

## Public API
- `new_workflow(workflow_name: str, workflow_path: str = ".", extra_values: dict = {})`
  - Converts `workflow_name` to PascalCase.
  - Ensures `workflow_path` exists (creates it if missing; `"."` resolves to current working directory).
  - Copies the workflow template into `workflow_path` using `Copier`, passing template values.

- CLI command: `new workflow WORKFLOW_NAME [WORKFLOW_PATH]`
  - Invokes `new_workflow(WORKFLOW_NAME, WORKFLOW_PATH)`.

## Configuration/Dependencies
- **Dependencies**
  - `click` (CLI command/arguments)
  - `naas_abi_cli` (used to locate bundled templates)
  - `naas_abi_cli.cli.utils.Copier.Copier` (performs the template copy)
  - `.utils.to_pascal_case` (name normalization)

- **Template location**
  - Computed as: `os.path.join(os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/workflow")`

- **Template values passed**
  - `workflow_name_pascal`: PascalCase version of `workflow_name`
  - plus any `extra_values` merged in via `values | extra_values`

## Usage

### CLI
```bash
naas-abi new workflow MyWorkflow .
```

### Python
```python
from naas_abi_cli.cli.new.workflow import new_workflow

new_workflow("my_workflow", workflow_path=".")
```

## Caveats
- `extra_values` has a mutable default (`{}`), which can be shared across calls.
- `workflow_name` is converted to PascalCase before templating; the template receives `workflow_name_pascal` only.
