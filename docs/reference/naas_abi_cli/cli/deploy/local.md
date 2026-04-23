# `setup_local_deploy` (local deploy setup)

## What it is
Utilities to scaffold and maintain a local deployment layout for an ABI project:
- Renders `.deploy/` from packaged templates.
- Moves generated `docker-compose.yml` and `.env` to the project root.
- Ensures required environment variables exist (and generates secrets).
- Optionally adds a Headscale service and its configuration.

## Public API
- `setup_local_deploy(project_path: str, include_headscale: bool = False, base_domain: str | None = None, regenerate: bool = False, backup: bool = True) -> None`
  - Creates/updates local deploy files under `project_path`.
  - Prompts for a base domain if `base_domain` is not provided.
  - If `regenerate=True`, can back up existing deploy artifacts and re-render templates.
  - If `include_headscale=True`, renders Headscale templates and injects a `headscale` service into `docker-compose.yml` (if not already present).

> Other functions/constants in this module are internal helpers.

## Configuration/Dependencies
- **Template source**: uses `Copier` (from `..utils.Copier`) to render templates located inside the installed `naas_abi_cli` package:
  - `cli/deploy/templates/local`
  - `cli/deploy/templates/local/docker/headscale` (when Headscale is enabled)
- **Interactive input**: `rich.prompt.Prompt.ask` is used when `base_domain` is omitted.
- **Backups** (when `regenerate=True` and `backup=True`):
  - Writes to: `.abi-backups/deploy-local/<timestamp>/`
  - Backs up any existing: `.deploy/`, `docker-compose.yml`, `.env`
- **Key environment defaults**:
  - Uses `DEFAULT_ENV_VALUES` and computed hosts from `base_domain`:
    - `PUBLIC_WEB_HOST = nexus.<base_domain>`
    - `PUBLIC_API_HOST = api.<base_domain>`
    - Headscale (if enabled): `headscale.<base_domain>`, `vpn.<base_domain>`
  - Generates random UUID secrets for:
    - `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `RABBITMQ_PASSWORD`, `FUSEKI_ADMIN_PASSWORD`
- **NEXUS_API_URL derivation**:
  - Built from `PUBLIC_API_HOST` and optional `PUBLIC_API_SCHEME`.
  - Defaults scheme to `http` for localhost/IP hosts, otherwise `https`.
  - If host has no explicit port and is localhost/IP, appends port `9879`.

## Usage
Minimal (non-interactive) usage from Python:

```python
from naas_abi_cli.cli.deploy.local import setup_local_deploy

setup_local_deploy(
    project_path=".",
    base_domain="localhost",
    include_headscale=False,
    regenerate=False,
)
```

Regenerate and include Headscale (with backup):

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

## Caveats
- If `include_headscale=True` and the target `docker-compose.yml` exists but does **not** contain a `volumes:` section, Headscale injection raises `ValueError`.
- Headscale template rendering must produce:
  - `.deploy/docker/headscale/config.yaml`
  - `.deploy/docker/headscale/extra-records.json`
  Otherwise `FileNotFoundError` is raised.
- When **not** regenerating, `.deploy/.env` content is appended to the project `.env` only once (guarded by a marker line). Subsequent runs won’t re-append that block.
- When `regenerate=True`, the `.env` is rewritten using the new template while preserving existing values where keys match, and appending non-template keys under “Preserved custom values from previous .env”.
