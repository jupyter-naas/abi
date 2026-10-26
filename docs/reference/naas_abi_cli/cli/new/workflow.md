# `new_workflow`

## What it is
- Implements the `naas-abi-cli new workflow` command.
- Scaffolds a workflow from a bundled template into a target path, for the kind of module it runs in: a `naas_abi_core` workflow in an in-engine module, a `naas_abi_sdk` one in a remote module.

## Public API
- `new_workflow(workflow_name: str, workflow_path: str = ".", extra_values: dict | None = None, remote: bool = False)`
  - Converts `workflow_name` to PascalCase.
  - Resolves `workflow_path` (`"."` becomes `os.getcwd()`) and creates the directory if it does not exist.
  - With `remote=True`, makes the folder a package (`ensure_package`): the scaffold's test imports the class relatively, and the module imports it by its dotted name.
  - Copies the templates, chosen by `remote`:
    - `remote=False` → `cli/new/templates/workflow`
    - `remote=True` → `cli/new/templates/remote_workflow` (imports `naas_abi_sdk` only, with a `<Name>Workflow_test.py` beside it)
  - Template values: `workflow_name_pascal`, `workflow_name_snake` and `workflow_name_upper`, merged with `extra_values` (dict union `|`).

- Click command: `naas-abi-cli new workflow WORKFLOW_NAME [WORKFLOW_NAME_PATH]`
  - `_new_workflow` detects the target with `is_remote_module(target_dir(workflow_path))` and calls `new_workflow(..., remote=remote)`.
  - In a remote module it prints what to do next: the module builds the workflow after `on_initialized` under its snake-case class name, other modules start it as the durable workflow `workflow.<name>` (the module declares the `document` service), and an agent needs `await self.build_processes()` before `self.get_workflow_instance(name).as_tools()`; it needs the `naas-abi-sdk[workflows]` extra.
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
naas-abi-cli new workflow MyWorkflow .
```

### Python
```python
from naas_abi_cli.cli.new.workflow import new_workflow

new_workflow("my_workflow", "./out")                 # naas_abi_core
new_workflow("my_workflow", "./out", remote=True)    # naas_abi_sdk
```

## Caveats
- If `workflow_path == "."`, it is replaced with `os.getcwd()`.
- `workflow_name` is converted to PascalCase; the template receives it under `workflow_name_pascal`.
- The remote scaffold's `run` is `async`; other modules call the workflow over NATS and it can declare `job = JobSettings(...)`.
