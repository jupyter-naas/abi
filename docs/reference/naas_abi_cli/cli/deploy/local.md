# `setup_local_deploy`

## What it is

Utilities to scaffold and maintain a local deployment layout for an ABI project:

- Renders `.deploy/` from packaged templates.
- Moves generated `docker-compose.yml` to the project root (if not already present).
- Appends or regenerates `.env` at the project root from the `.deploy/.env` template.
- Ensures required environment variables exist (generates secrets where needed).
- Optionally:
  - Adds Headscale templates and injects a `headscale` service into `docker-compose.yml`.
  - Adds “coding” templates and writes additional `CODER_*` / `FORGEJO_*` env vars.
- Supports NATS vs “classic” stack selection (RabbitMQ/Dagster legacy).

## Public API

- `setup_local_deploy(project_path: str, include_headscale: bool = False, include_coding: bool = False, base_domain: str | None = None, regenerate: bool = False, backup: bool = True, nats: bool | None = None) -> None`
  - Main entrypoint to generate/update local deploy artifacts.
  - Prompts for `base_domain` if not provided.
  - When `regenerate=True`, re-renders templates, optionally backing up existing files.
  - When `nats=None`, auto-detects NATS usage from project config (see below).
  - Always ensures `.env` contains required defaults and secrets.

- `project_uses_nats(project_path: str) -> bool | None`
  - Returns whether the project’s runtime config uses NATS:
    - Looks for a top-level `nats:` block in `config.local.yaml` first, else `config.yaml`.
    - Returns `None` if neither config file exists.

- `any_config_uses_nats(project_path: str) -> bool`
  - Returns `True` if **either** `config.local.yaml` or `config.yaml` contains a top-level `nats:` block.

- `legacy_extras_requirement(project_path: str) -> str | None`
  - Reads `pyproject.toml` and determines whether `naas-abi-core` dependency lacks legacy extras `dagster` and `rabbitmq`.
  - Returns an updated requirement string adding missing extras, or `None` if not applicable.

- `ensure_legacy_extras(project_path: str) -> None`
  - Runs `uv add <requirement>` (if `uv` is available) to add `dagster` and `rabbitmq` extras when needed.

## Configuration/Dependencies

- **Templates**
  - Base local deploy templates are rendered into `.deploy/` via `Copier`:
    - `naas_abi_cli/cli/deploy/templates/local`
  - Headscale templates (when enabled):
    - `naas_abi_cli/cli/deploy/templates/local/docker/headscale`
  - Coding templates (when enabled):
    - `naas_abi_cli/cli/deploy/templates/coding`

- **Interactive input**
  - Uses `rich.prompt.Prompt.ask` when `base_domain` is not provided.

- **Backups**
  - When `regenerate=True` and `backup=True`, existing paths are copied to:
    - `.abi-backups/deploy-local/<YYYYMMDD-HHMMSS>/`
  - Backed up (if present):
    - `.deploy/`, `docker-compose.yml`, `.env`

- **Stack mode (NATS vs classic)**
  - `setup_local_deploy(..., nats=None)`:
    - Uses `project_uses_nats()`.
    - If no config exists yet, defaults to `nats=True`.
    - If config exists and has no `nats:` block, keeps classic stack and prints a migration notice.

- **Environment population**
  - Defaults come from `DEFAULT_ENV_VALUES`.
  - Per-run UUIDs are generated for (and ensured present in `.env`):
    - `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `RABBITMQ_PASSWORD`,
      `FUSEKI_ADMIN_PASSWORD`, `ABI_API_KEY`
  - Admin / NATS helpers are invoked:
    - `ensure_admin_credentials(...)`
    - `ensure_nats_passwords(...)`
    - `ensure_nats_secret(...)` (only if `nats=True`)
  - `NEXUS_API_URL` is derived from:
    - `PUBLIC_API_HOST` and optional `PUBLIC_API_SCHEME`
    - Defaults scheme to `http` for localhost/IP, otherwise `https`
    - If host has no explicit port and is localhost/IP, appends port `9879`

- **Headscale docker-compose injection**
  - If enabled and `docker-compose.yml` exists:
    - Inserts a `headscale` service snippet before the `volumes:` section.
    - Adds `headscale_data` and `headscale_run` named volumes if missing.

## Usage

Minimal non-interactive usage:

```python
from naas_abi_cli.cli.deploy.local import setup_local_deploy

setup_local_deploy(
    project_path=".",
    base_domain="localhost",
    include_headscale=False,
    include_coding=False,
    regenerate=False,
)
```

Regenerate (with backup) and include Headscale:

```python
from naas_abi_cli.cli.deploy.local import setup_local_deploy

setup_local_deploy(
    project_path=".",
    base_domain="example.localhost",
    include_headscale=True,
    regenerate=True,
    backup=True,
)
```

Force classic stack (no NATS), and include coding templates:

```python
from naas_abi_cli.cli.deploy.local import setup_local_deploy

setup_local_deploy(
    project_path=".",
    base_domain="localhost",
    nats=False,
    include_coding=True,
)
```

## Caveats

- If `.env` exists but is not writable, `setup_local_deploy` fails early with a `click.ClickException` (e.g., file ownership changed by a root-run container).
- Headscale compose injection requires `docker-compose.yml` to contain a `volumes:` section; otherwise `_ensure_headscale_service` raises `ValueError`.
- Headscale template rendering must produce:
  - `.deploy/docker/headscale/config.yaml`
  - `.deploy/docker/headscale/extra-records.json`
  Otherwise `_copy_headscale_templates` raises `FileNotFoundError`.
- When `regenerate=False`, `.deploy/.env` content is appended to the project `.env` only once (guarded by `# Added by abi deploy local command execution`).
- When `regenerate=True`, `.env` is rewritten by merging the new template with existing values:
  - Template keys keep existing values when present.
  - Non-template keys are appended under `# Preserved custom values from previous .env`.
