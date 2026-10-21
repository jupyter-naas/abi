# `new_module`

## What it is
Creates a new ABI module scaffold on disk.

- Exposed as a Click subcommand: `new module`
- Exposed as a Python function: `new_module(...)`
- Supports two kinds of modules:
  - **remote**: an SDK module (in-project under `src/` or as a standalone repository)
  - **in-engine**: a “classic” module loaded by the engine (creates agents/integrations/etc.)

## Public API

### CLI command
- `naas-abi-cli new module MODULE_NAME [MODULE_PATH]`
  - Implemented by `_new_module(...)` and registered via `@new.command("module")`.
  - Options:
    - `--in-engine/--local`: force an in-engine module.
    - `--remote`: force a remote module (in-project if possible).
    - `--standalone`: create a remote module as its own repository.
    - `--abi-ref <ref>`: only relevant with `--standalone`; controls the ABI git ref used by the standalone scaffold.
  - Constraint:
    - `--in-engine` cannot be combined with `--remote` or `--standalone` (raises `click.UsageError`).

### Functions
- `new_module(module_name: str, module_path: str = ".", quiet: bool = False, kind: Literal["remote","in-engine"] | None = None, standalone: bool = False, abi_ref: str | None = None, orchestration: bool | None = None)`
  - Normalizes `module_name` to **kebab-case**.
  - Auto-selects module kind when `kind is None`:
    - **in-engine** if inside a project, not standalone, and the project has no NATS configured (`not project.nats_anywhere()`).
    - otherwise **remote**.
  - **Remote** behavior:
    - If `standalone` or not inside a project:
      - Creates a standalone repository at `<base>/<module_name>` where `base` is `cwd` if `module_path == "."` else `module_path`.
      - Uses `create_standalone(module_name, repository, abi_ref or default_abi_git_ref())`.
    - Else (inside a project):
      - Creates under the project’s package directory (via `default_package_dir(...)`).
      - Uses `create_in_project(project, module_name, package)`.
    - Returns immediately after remote creation.
  - **In-engine** behavior:
    - Creates package directory (via `default_package_dir(...)`) and copies templates from `cli/new/templates/module` using `Copier`.
    - Generates subcomponents into the module directory:
      - `new_agent(..., "<module>/agents", extra_values={"module_name_snake": ...})`
      - `new_integration(..., "<module>/integrations", ...)`
      - `new_pipeline(..., "<module>/pipelines", ...)`
      - `new_workflow(..., "<module>/workflows", ...)`
      - `new_app(..., "<module>/apps", ...)`
      - Orchestration handling (see below).
    - Prints config.yaml enablement instructions unless `quiet=True`.
- `_empty_destination(path: str) -> None`
  - Ensures `path` exists and is empty.
  - If `path` exists and is non-empty: prints an error and terminates the process with `sys.exit(1)`.

## Configuration/Dependencies

- **Filesystem**
  - Creates directories and writes files under the resolved destination.
  - Aborts if destination exists and is non-empty.

- **Project detection**
  - Uses `find_project(Path(os.getcwd()))` to detect an ABI project.
  - Uses `project.nats_anywhere()` to decide defaults (remote vs in-engine, orchestration default).

- **Templates**
  - In-engine modules copy templates from:
    - `<naas_abi_cli package>/cli/new/templates/module`

- **Key dependencies**
  - `click` (CLI)
  - `naas_abi_cli` (template path resolution)
  - `Copier` (template copier utility)
  - Component generators: `new_agent`, `new_integration`, `new_pipeline`, `new_workflow`, `new_orchestration`, `new_app`
  - Remote module helpers: `create_in_project`, `create_standalone`, `default_abi_git_ref`, `default_package_dir`, `find_project`

## Usage

### Python
```python
from naas_abi_cli.cli.new.module import new_module

new_module("my-module", module_path=".", quiet=True)
```

### CLI
```bash
naas-abi-cli new module my-module .
```

Standalone remote module repository:
```bash
naas-abi-cli new module my-module . --standalone
```

## Caveats
- Destination folder must be empty; otherwise the process exits via `sys.exit(1)`.
- Orchestrations directory behavior for in-engine modules:
  - If `orchestration is None`: it defaults to `True` when outside a project or when the project has no NATS; otherwise `False`.
  - When `False`, the generated `orchestrations/` folder is deleted (`shutil.rmtree(...)`).
- Printed enablement instructions compute a Python import namespace relative to either:
  - `project.src` when creating in the project with `module_path == "."`, or
  - the current working directory otherwise.
