# `new_project`

## What it is
A `click` command (`new project`) that scaffolds a new Naas ABI project directory from templates, creates an initial module under `src/`, optionally generates local deployment scaffolding, installs dependencies via `uv`, and validates ABI configuration.

## Public API
- `new_project(project_name: str | None, project_path: str | None, with_local_deploy: bool, with_headscale: bool)`
  - Registered as `new project` under the `new` command group.
  - Responsibilities:
    - Normalize and default `project_name`/`project_path`.
    - Ensure target directory exists and is empty.
    - Copy project template files into destination.
    - Create a module in `<project_path>/src` via `new_module(..., quiet=True)`.
    - Optionally run `setup_local_deploy(..., include_headscale=...)`.
    - Run `uv add ...` to install dependencies.
    - Run `uv run abi config validate` to validate configuration.

CLI inputs:
- Arguments:
  - `project-name` (optional): Project name; converted to kebab-case. Defaults to current directory name.
  - `project-path` (optional): Base path; defaults to current working directory.
- Options:
  - `--with-local-deploy / --without-local-deploy` (default: enabled)
  - `--with-headscale / --without-headscale` (default: disabled)

## Configuration/Dependencies
- Template source directory (internal):
  - `<naas_abi_cli package>/cli/new/templates/project`
- External commands executed (must be available in `PATH`):
  - `uv` (used for `uv add` and `uv run ...`)
  - `abi` (invoked via `uv run abi config validate`)
- Python-level dependencies used:
  - `click`
  - `naas_abi_cli`
  - `naas_abi_cli.cli.deploy.local.setup_local_deploy`
  - `naas_abi_cli.cli.utils.Copier.Copier`
  - `new_module` from sibling module

Dependencies installed into the generated project (via `uv add`):
- `naas-abi-core[all]`
- `naas-abi-marketplace[ai-chatgpt]`
- `naas-abi`
- `naas-abi-cli`

## Usage
Run via the CLI entrypoint that exposes the `new` command group:

```bash
# Create a project in ./my-project (folder will be created if missing)
abi new project my-project .

# Create using defaults (name = current folder name, path = current folder)
abi new project

# Disable local deploy scaffolding
abi new project my-project . --without-local-deploy

# Include headscale in local deploy scaffolding
abi new project my-project . --with-headscale
```

## Caveats
- The destination folder must be empty; if it exists and contains files, the command prints an error and exits with code `1`.
- `project_path` is normalized to an absolute path, and the final directory is forced to end with the (kebab-cased) `project_name`.
- The command runs `uv` subprocesses with `check=True`; failures in dependency install or config validation will raise an error and stop execution.
