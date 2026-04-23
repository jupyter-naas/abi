# `new_module` (module scaffolding)

## What it is
Creates a new “module” directory scaffold from templates and generates default subcomponents (agent, integration, pipeline, workflow, orchestration). Exposed both as a Click subcommand and as a callable Python function.

## Public API
- `new_module(module_name: str, module_path: str = ".", quiet: bool = False)`
  - Normalizes `module_name` to kebab-case.
  - Resolves the target directory:
    - If `module_path == "."`: `<cwd>/<module_name_snake>/`
    - Else: `<module_path>/<module_name_snake>/`
  - Creates the directory (fails if it exists and is non-empty).
  - Copies template files from the package templates directory into the destination.
  - Generates subfolders and scaffolds:
    - `agents/` via `new_agent(...)`
    - `integrations/` via `new_integration(...)`
    - `pipelines/` via `new_pipeline(...)`
    - `workflows/` via `new_workflow(...)`
    - `orchestrations/` via `new_orchestration(...)`
  - If `quiet` is `False`, prints post-create instructions including a `config.yaml` snippet.

- Click command: `new module MODULE_NAME [MODULE_PATH]`
  - Implemented by `_new_module(...)` and registered under `@new.command("module")`.
  - Calls `new_module(module_name, module_path)`.

## Configuration/Dependencies
- **Filesystem**
  - Creates directories with `os.makedirs(...)`.
  - Refuses to proceed if the destination folder exists and is not empty.
- **Third-party / internal**
  - `click` for CLI wiring.
  - `Copier` from `naas_abi_cli.cli.utils.Copier` to copy templates.
  - Template source directory:
    - `os.path.join(os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/module")`
  - Name normalization helpers:
    - `to_kebab_case`, `to_snake_case`, `to_pascal_case`
  - Sub-scaffold creators:
    - `new_agent`, `new_integration`, `new_pipeline`, `new_workflow`, `new_orchestration`

## Usage

### From Python
```python
from naas_abi_cli.cli.new.module import new_module

new_module("My Module", module_path=".", quiet=True)
```

### From CLI
```bash
naas-abi-cli new module "my-module" .
```

## Caveats
- If the target directory already exists and is **not empty**, the function prints an error and terminates the process with `exit(1)`.
- `module_path` is treated as a base directory; the final folder name is always derived from `module_name` converted to snake-case.
