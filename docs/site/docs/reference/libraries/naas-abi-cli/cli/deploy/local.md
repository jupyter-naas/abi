# `setup_local_deploy` (naas_abi_cli.cli.deploy.local)

## What it is
Utilities to scaffold and configure a local ABI deployment in a project directory by:
- Copying `.deploy` template assets into the project (once)
- Moving generated `docker-compose.yml` to the project root (if not already present)
- Appending/creating `.env` entries in the project root
- Optionally adding Headscale templates and a Headscale service into `docker-compose.yml`

## Public API
- `setup_local_deploy(project_path: str, include_headscale: bool = False, base_domain: str | None = None) -> None`
  - Main entry point to set up local deployment files and environment variables under `project_path`.
  - Prompts for `base_domain` if not provided.
  - Generates hostnames from `base_domain`:
    - `PUBLIC_WEB_HOST` = `nexus.<base_domain>`
    - `PUBLIC_API_HOST` = `api.<base_domain>`
    - If `include_headscale=True`:
      - `HEADSCALE_SERVER_URL` = `headscale.<base_domain>`
      - `HEADSCALE_INTERNAL_DOMAIN` = `vpn.<base_domain>`
  - Computes `NEXUS_API_URL` from `PUBLIC_API_HOST` (adds port for localhost/IP when needed).

## Configuration/Dependencies
- File system layout expected/produced:
  - `<project_path>/.deploy/` (created from templates if missing)
  - `<project_path>/docker-compose.yml` (moved from `.deploy/docker-compose.yml` if not already present)
  - `<project_path>/.env` (appended/created)
- Template sources (inside the installed `naas_abi_cli` package):
  - `cli/deploy/templates/local`
  - `cli/deploy/templates/local/docker/headscale` (only when `include_headscale=True`)
- External dependencies used:
  - `rich.prompt.Prompt` for interactive `base_domain` prompt when `base_domain=None`
  - `Copier` from `naas_abi_cli.cli.utils.Copier` to copy template directories

## Usage
```python
from naas_abi_cli.cli.deploy.local import setup_local_deploy

# Non-interactive
setup_local_deploy(
    project_path=".",
    include_headscale=True,
    base_domain="localhost",
)
```

## Caveats
- Headscale docker-compose injection requires an existing `docker-compose.yml` with a `volumes:` section; otherwise `_ensure_headscale_service` raises:
  - `ValueError("Unable to add headscale service: docker compose volumes section missing")`
- Existing `.env` keys are not overwritten; if a key already exists, it is left unchanged.
- Random secrets (`POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `RABBITMQ_PASSWORD`, `FUSEKI_ADMIN_PASSWORD`) are generated with `uuid4()` but only written if missing.
- If `<project_path>/docker-compose.yml` already exists, the templated `.deploy/docker-compose.yml` is deleted rather than merged.
