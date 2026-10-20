# `new_project`

## What it is

A `click` CLI command (`abi new project`) that scaffolds a new Naas ABI project directory from templates, optionally adds local deployment scaffolding, seeds required secrets into `.env`, installs dependencies with `uv`, validates configuration, and prints next steps.

## Public API

- `new_project(project_name: str | None, project_path: str | None, with_local_deploy: bool, with_headscale: bool, with_coding: bool, with_abi_submodule: bool, with_nats: bool, base_domain: str) -> None`
  - Registered as the `project` subcommand under the `new` click command group.
  - Responsibilities:
    - Normalize `project_name` to kebab-case; default to current directory name.
    - Normalize `project_path` to an absolute path; default to current working directory.
    - Ensure `project_path` ends with the resolved `project_name`.
    - Create the destination directory if missing; abort if it exists and is non-empty.
    - Optionally add the upstream ABI repo as a git submodule at `.abi/` (default enabled).
    - Render project templates into the destination.
    - Create an initial in-engine module under `<project_path>/src` via `new_module(...)`.
    - Optionally generate local deploy scaffolding via `setup_local_deploy(...)`.
    - Seed `.env` with:
      - admin credentials (always)
      - NATS secret and NATS user passwords (when `--with-nats`)
    - Install dependencies via `uv add ...`.
    - Validate config via `uv run abi config validate`.
    - Print a short “next steps” guide (including `abi dev up`).

Internal helpers (module-level; not exposed as CLI commands):

- `_add_abi_submodule(project_path: str) -> bool`
  - Adds `https://github.com/jupyter-naas/abi.git` as a git submodule at `.abi/`.
  - Returns `True` only if `.abi/libs` exists (usable as a dependency source); failures are non-fatal unless NATS mode requires it.
- `_cd_argument(project_path: str) -> str`
  - Returns a quoted `cd` target (relative when appropriate, absolute otherwise).
- `_print_next_steps(project_path: str, admin_email: str, nats: bool) -> None`
  - Prints where the project was created and how to start it; includes NATS-specific notes when applicable.

### CLI parameters/options

- Arguments:
  - `project-name` (optional; defaults to current directory name)
  - `project-path` (optional; defaults to current working directory)
- Options:
  - `--with-local-deploy / --without-local-deploy` (default: enabled)
  - `--with-headscale / --without-headscale` (default: disabled)
  - `--with-coding / --without-coding` (default: disabled)
  - `--with-abi-submodule / --without-abi-submodule` (default: enabled)
  - `--with-nats / --without-nats` (default: enabled)
  - `--domain` / `base_domain` (prompted; default: `localhost`)
    - Sets `BASE_DOMAIN` and derives `PUBLIC_WEB_HOST` and `PUBLIC_API_HOST` via `_build_hosts_from_domain(...)`.

## Configuration/Dependencies

- Templates are loaded from:
  - `<naas_abi_cli package>/cli/new/templates/project`
- External executables expected on `PATH`:
  - `uv` (required; used to add dependencies and run `abi config validate`)
  - `git` (optional; required only to add the `.abi` submodule)
- Internal dependencies:
  - `Copier` (template rendering)
  - `new_module` (creates the initial module in `src/`)
  - `setup_local_deploy` and `_build_hosts_from_domain` (local deploy scaffolding and host derivation)
  - `.env` helpers:
    - `ensure_admin_credentials` (always)
    - `ensure_nats_secret`, `ensure_nats_passwords` (NATS mode)
  - Naming helpers: `to_kebab_case`, `to_snake_case`, `to_pascal_case`
  - `LEGACY_EXTRAS` (used when `--without-nats` to include legacy core extras)

## Usage

Shell examples:

```bash
# Create a project in ./my-project (folder created if missing)
abi new project my-project .

# Create a project at /tmp/my-project without local deploy scaffolding
abi new project my-project /tmp --without-local-deploy

# Include headscale in local deploy scaffolding
abi new project my-project . --with-headscale

# Create a classic (non-NATS) project
abi new project my-project . --without-nats

# Set a custom base domain (also threaded into local deploy scaffolding when enabled)
abi new project my-project . --domain example.test
```

## Caveats

- Destination directory must be empty:
  - If it exists and contains files, the command prints a message and exits with code `1`.
- NATS projects require the `.abi` submodule:
  - `--with-nats --without-abi-submodule` raises a `click.UsageError`.
  - If submodule add fails in a newly-created directory, the directory is removed and the command errors.
- Dependency install and config validation are strict:
  - `uv add ...` and `uv run abi config validate` run with `check=True` and will stop execution on failure.
- NATS runtime requirement:
  - The printed next steps note that `abi dev up` needs `nats-server` on `PATH` when `--with-nats` is enabled.
