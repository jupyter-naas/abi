# `deploy` (CLI group)

## What it is
A Click-based CLI module that supports:
- Deploying the current project as a Docker image to a Naas space (`deploy naas`)
- Generating and running a local Docker Compose deployment (`deploy local`, `deploy local-up`, `deploy local-down`, `deploy local-logs`)

It also includes a minimal Naas API client and a deployer that builds/pushes an image and creates/updates a Naas space.

## Public API

### CLI commands
- `deploy` (Click group)
  - Root command group.

- `deploy naas --env <env>`
  - Loads configuration for `env`, builds an image, pushes to a Naas registry, and creates/updates a Naas space.

- `deploy local --env <env> [--regenerate] [--no-backup] [--headscale] [--coding]`
  - Writes the project’s docker-compose stack via `setup_local_deploy(...)`.
  - If the project does **not** use NATS, it ensures legacy extras are present via `ensure_legacy_extras(...)`.

- `deploy local-up [--detach]`
  - Runs `docker compose up` using:
    - `docker-compose.yml`
    - optionally `docker-compose.override.yml` (if it exists)
    - `.env` as env-file
    - profiles: `infrastructure` and `container`

- `deploy local-down [--volumes]`
  - Runs `docker compose down` with the same compose files/profiles; optionally removes volumes.

- `deploy local-logs`
  - Runs `docker compose logs -f` with the same compose files/profiles.

### Classes
- `Container` (`pydantic.BaseModel`)
  - Fields: `name: str`, `image: str`, `port: int`, `cpu: str`, `memory: str`, `env: dict`
  - Represents a container definition for a Naas Space payload.

- `Space` (`pydantic.BaseModel`)
  - Fields: `name: str`, `containers: list[Container]`
  - Represents a space definition for a Naas Space payload.

- `NaasAPIClient`
  - `__init__(naas_api_key: str)`
    - Sets API key and base URL `https://api.naas.ai`.
  - `create_registry(name: str) -> dict`
    - `POST /registry/`; on `409` falls back to `get_registry`.
  - `get_registry(name: str) -> dict`
    - `GET /registry/{name}`.
  - `get_registry_credentials(name: str) -> dict`
    - `GET /registry/{name}/credentials`.
  - `create_space(space: Space) -> dict`
    - `POST /space/`; on `409` calls `update_space`; on `402` raises `click.ClickException`.
  - `update_space(space: Space) -> dict`
    - `PUT /space/{space.name}`.
  - `get_space(name: str) -> dict`
    - `GET /space/{name}`.

- `NaasDeployer`
  - `__init__(configuration: EngineConfiguration)`
    - Requires `configuration.deploy` (else raises `click.ClickException`).
    - Instantiates `NaasAPIClient` with `configuration.deploy.naas_api_key`.
  - `docker_build(image_name: str) -> None`
    - Runs: `docker build -t <image_name> . --platform linux/amd64`.
  - `deploy() -> None`
    - End-to-end deploy:
      - create/get registry
      - build image (tagged with a UUID)
      - get registry credentials and `docker login`
      - `docker push`
      - extract pushed image digest via `docker inspect ... | cut ...`
      - create/update space with a single `api` container (port `9879`, cpu `1`, memory `1Gi`, env from config)
      - prints a success message (space, image, URL)

### Functions
- `_get_configuration(env: str) -> EngineConfiguration`
  - Sets `os.environ["ENV"] = env`, loads configuration via `EngineConfiguration.load_configuration()`, and validates `configuration.deploy` is present.

## Configuration/Dependencies

### Configuration
- Loads configuration via `EngineConfiguration.load_configuration()`.
- Requires `configuration.deploy` to exist; used fields include:
  - `naas_api_key`
  - `space_name`
  - `env` (dict passed to the deployed container as environment)

### External dependencies
- Docker CLI required for:
  - `docker build`, `docker login`, `docker push`, `docker inspect`
  - `docker compose up/down/logs`
- Network access to `https://api.naas.ai` for registry/space operations.
- Imports rely on:
  - `click`, `requests`, `pydantic`, `rich`, `naas_abi_core`
  - local module: `.local` (`setup_local_deploy`, `project_uses_nats`, `ensure_legacy_extras`)

## Usage

### CLI
```bash
# Deploy to Naas using prod config
naas-abi-cli deploy naas --env prod

# Generate local compose stack
naas-abi-cli deploy local --env local

# Generate local compose stack, including Headscale and coding services
naas-abi-cli deploy local --env local --headscale --coding

# Start local stack
naas-abi-cli deploy local-up --detach

# Follow logs
naas-abi-cli deploy local-logs

# Stop local stack and remove volumes
naas-abi-cli deploy local-down --volumes
```

### Minimal Python example (Naas API client)
```python
from naas_abi_cli.cli.deploy.deploy import NaasAPIClient

client = NaasAPIClient(naas_api_key="YOUR_NAAS_API_KEY")
print(client.get_space("your-space-name"))
```

## Caveats
- Docker subprocess calls use `check=False`; failures may not raise Python exceptions automatically.
- Image digest extraction uses `shell=True` with a pipeline (`docker inspect ... | cut ...`).
- Naas deployment is hardcoded to create/update a space with a single container:
  - name: `api`
  - port: `9879`
  - cpu: `1`
  - memory: `1Gi`
- Local compose commands assume `docker-compose.yml` and `.env` exist in the current working directory; `docker-compose.override.yml` is included only if present.
