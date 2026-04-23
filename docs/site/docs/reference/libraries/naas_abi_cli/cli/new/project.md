# `new_project`

## What it is
A `click` command (`new project`) that scaffolds a new Naas ABI project directory from templates, generates an initial module, optionally adds local deployment scaffolding, and installs/validates dependencies using `uv`.

## Public API
- `new_project(project_name: str | None, project_path: str | None, with_local_deploy: bool, with_headscale: bool)`
  - CLI command registered as `new project` under the `new` command group.
  - Responsibilities:
    - Normalize `project_name` to kebab-case.
    - Determine/normalize the target `project_path` and ensure it ends with the project name.
    - Create the target directory (fails if it exists and is non-empty).
    - Copy project templates into the destination using `Copier`.
    - Create a module under `<project_path>/src` via `new_module(..., quiet=True)`.
    - Optionally generate local deploy scaffolding via `setup_local_deploy(..., include_headscale=...)`.
    - Run:
      - `uv add naas-abi-core[all] naas-abi-marketplace[ai-chatgpt] naas-abi naas-abi-cli`
      - `uv run abi config validate`

### CLI parameters/options
- Arguments:
  - `project-name` (optional; defaults to current directory name)
  - `project-path` (optional; defaults to current working directory)
- Options:
  - `--with-local-deploy / --without-local-deploy` (default: enabled)
  - `--with-headscale / --without-headscale` (default: disabled)

## Configuration/Dependencies
- Uses template files located at:
  - `<naas_abi_cli package>/cli/new/templates/project`
- Relies on:
  - `uv` executable available on `PATH` (used via `subprocess.run`)
  - Internal helpers:
    - `Copier` for template copying
    - `new_module` for module creation
    - `setup_local_deploy` for docker-compose/deploy scaffolding
    - `to_kebab_case`, `to_snake_case`, `to_pascal_case` for naming

## Usage
Minimal CLI usage (from a shell):
```bash
# Create a project in ./my-project (folder created if missing)
abi new project my-project .

# Create a project at /tmp/my-project without local deploy scaffolding
abi new project my-project /tmp --without-local-deploy

# Include headscale in local deploy scaffolding
abi new project my-project . --with-headscale
```

## Caveats
- The destination folder must be empty; if it exists and contains files, the command prints a message and exits with code `1`.
- The command runs `uv add ...` and `uv run abi config validate` with `check=True`; failures raise an exception and stop execution.
- `project_path` is forced to end with the resolved `project_name` (it appends the name if the last path component doesn’t match).
