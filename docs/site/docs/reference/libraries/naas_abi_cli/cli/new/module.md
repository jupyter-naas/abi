# new_module

## What it is
Creates a new “module” project scaffold on disk from templates, and generates default subcomponents (agent, integration, pipeline, workflow, orchestration) under the module directory. Exposed both as a Click CLI subcommand and as a Python function.

## Public API
- `new_module(module_name: str, module_path: str = ".", quiet: bool = False)`
  - Normalizes `module_name` to kebab-case.
  - Resolves the destination folder as `<module_path>/<module_name_snake>` (or `cwd/<module_name_snake>` when `module_path == "."`).
  - Creates the destination directory (fails if it exists and is non-empty).
  - Copies module templates into the destination via `Copier`.
  - Generates subfolders/components using:
    - `new_agent(..., "<module_path>/agents", extra_values=...)`
    - `new_integration(..., "<module_path>/integrations", extra_values=...)`
    - `new_pipeline(..., "<module_path>/pipelines", extra_values=...)`
    - `new_workflow(..., "<module_path>/workflows", extra_values=...)`
    - `new_orchestration(..., "<module_path>/orchestrations", extra_values=...)`
  - Prints post-create instructions unless `quiet=True`.

- CLI command: `new module`
  - Defined by `_new_module(module_name, module_path=".")` and registered as a subcommand of `new`:
    - `@new.command("module")`
    - Arguments:
      - `module_name` (required)
      - `module_path` (optional, default `"."`)
  - Delegates to `new_module(module_name, module_path)`.

## Configuration/Dependencies
- **Filesystem**
  - Creates directories and writes files under the resolved `module_path`.
- **Templates**
  - Copies from: `.../cli/new/templates/module` inside the installed `naas_abi_cli` package.
- **Dependencies**
  - `click` (CLI parsing)
  - `naas_abi_cli` (to locate templates)
  - `Copier` (template copy utility)
  - Name helpers: `to_kebab_case`, `to_snake_case`, `to_pascal_case`
  - Component generators: `new_agent`, `new_integration`, `new_pipeline`, `new_workflow`, `new_orchestration`

## Usage

### Python
```python
from naas_abi_cli.cli.new.module import new_module

new_module("My Module", module_path=".", quiet=True)
```

### CLI
```bash
naas-abi-cli new module "my-module" .
```

## Caveats
- If the destination folder already exists **and is not empty**, the function prints an error and terminates the process with `exit(1)`.
- When `module_path == "."`, the destination is created under the current working directory, named with the **snake_case** form of `module_name`.
