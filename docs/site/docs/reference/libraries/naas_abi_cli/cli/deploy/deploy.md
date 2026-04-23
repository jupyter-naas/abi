# `deploy` (CLI group)

## What it is
A Click-based CLI module that provides deployment commands for:
- Deploying a Docker image to a Naas space (`deploy naas`)
- Generating and operating a local Docker Compose deployment (`deploy local`, `deploy local-up`, `deploy local-down`, `deploy local-logs`)

It also contains a small Naas API client and a deployer that builds/pushes an image and creates/updates a Naas space.

## Public API

### CLI commands
- `deploy` (Click group)
  - Root command group for subcommands below.
- `deploy naas --env <env>`
  - Loads configuration for `env`, builds a Docker image, pushes it to a Naas registry, and creates/updates a Naas space.
- `deploy local --env <env> [--regenerate] [--no-backup] [--headscale]`
  - Generates (and optionally regenerates) local deployment files via `setup_local_deploy(...)`.
- `deploy local-up [--detach]`
  - Runs `docker compose up` using `docker-compose.yml` and `.env` with profiles `infrastructure` and `container`.
- `deploy local-down [--volumes]`
  - Runs `docker compose down` with the same files/profiles; optionally removes volumes.
- `deploy local-logs`
  - Follows logs with `docker compose logs -f` (shell invocation).

### Classes
- `Container` (pydantic `BaseModel`)
  - Fields: `name`, `image`, `port`, `cpu`, `memory`, `env`.
  - Represents a container definition for a Naas space payload.
- `Space` (pydantic `BaseModel`)
  - Fields: `name`, `containers` (`list[Container]`).
  - Represents a space definition for a Naas space payload.
- `NaasAPIClient`
  - `__init__(naas_api_key: str)`: sets API key and uses base URL `https://api.naas.ai`.
  - `create_registry(name: str)`: `POST /registry/`; on `409` calls `get_registry`.
  - `get_registry(name: str)`: `GET /registry/{name}`.
  - `get_registry_credentials(name: str)`: `GET /registry/{name}/credentials`.
  - `create_space(space: Space)`: `POST /space/`; on `409` calls `update_space`; on `402` raises `click.ClickException`.
  - `update_space(space: Space)`: `PUT /space/{space.name}`.
  - `get_space(name: str)`: `GET /space/{name}`.
- `NaasDeployer`
  - `__init__(configuration: EngineConfiguration)`: requires `configuration.deploy` and instantiates `NaasAPIClient` with `configuration.deploy.naas_api_key`.
  - `docker_build(image_name: str)`: runs `docker build -t <image_name> . --platform linux/amd64`.
  - `deploy()`: end-to-end Naas deployment (registry creation, build/login/push, digest extraction, space create/update, prints success message).

### Functions (module-internal)
- `_get_configuration(env: str) -> EngineConfiguration`
  - Sets `ENV` environment variable, loads configuration via `EngineConfiguration.load_configuration()`, and validates `configuration.deploy` exists.

## Configuration/Dependencies

### Configuration
- Uses `EngineConfiguration.load_configuration()` and expects a non-`None` `configuration.deploy` section with at least:
  - `naas_api_key` (used for API auth)
  - `space_name` (used for registry and space name)
  - `env` (dict passed as container environment variables)

The `--env` option sets `os.environ["ENV"]` to select which config file to load (e.g., `config.prod.yaml`, `config.local.yaml`, etc., per the help text).

### External dependencies
- Docker CLI must be available for:
  - `docker build`, `docker login`, `docker push`, `docker inspect`
  - `docker compose up/down/logs`
- Python packages used: `click`, `requests`, `pydantic`, `rich`, `naas_abi_core`.

## Usage

### CLI
```bash
# Deploy to Naas using the "prod" environment config
naas-abi-cli deploy naas --env prod

# Generate local deployment files (optionally include headscale)
naas-abi-cli deploy local --env local --headscale

# Start local deployment
naas-abi-cli deploy local-up --detach

# Tail logs
naas-abi-cli deploy local-logs

# Stop local deployment (optionally remove volumes)
naas-abi-cli deploy local-down --volumes
```

### Minimal Python example (API client)
```python
from naas_abi_cli.cli.deploy.deploy import NaasAPIClient

client = NaasAPIClient(naas_api_key="YOUR_NAAS_API_KEY")
space = client.get_space("your-space-name")
print(space)
```

## Caveats
- Docker commands are invoked without checking return codes (`subprocess.run(...)` without `check=True`), so failures may not raise automatically.
- Image digest extraction uses a shell pipeline (`shell=True`) to parse `docker inspect` output.
- Naas deployment hardcodes container settings:
  - container name: `"api"`
  - port: `9879`
  - cpu: `"1"`
  - memory: `"1Gi"`
- Local commands assume `docker-compose.yml` and `.env` exist in the current working directory.
