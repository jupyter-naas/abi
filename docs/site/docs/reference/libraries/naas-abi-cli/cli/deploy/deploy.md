# deploy (CLI group)

## What it is
A `click`-based CLI module that provides deployment commands:
- Deploy the current project as a Docker image to **naas.ai** and create/update a **Space**
- Prepare and run a **local** deployment using Docker Compose

## Public API

### CLI entrypoints (Click commands)
- `deploy` (group): Root command group for deployment subcommands.
- `deploy naas --env <env>`: Builds, pushes a Docker image to a Naas-managed registry and creates/updates a Space.
- `deploy local --env <env>`: Sets up local deployment files in the current working directory via `setup_local_deploy(...)`.
- `deploy local-up [--detach]`: Runs Docker Compose with predefined profiles (`infrastructure`, `container`).
- `deploy local-down [--volumes]`: Stops Docker Compose services (optionally removes volumes).
- `deploy local-logs`: Tails Docker Compose logs.

### Data models (Pydantic)
- `Container`: Container specification sent to the Naas Space API.
  - Fields: `name`, `image`, `port`, `cpu`, `memory`, `env`
- `Space`: Space specification sent to the Naas Space API.
  - Fields: `name`, `containers`

### Clients / helpers
- `NaasAPIClient(naas_api_key: str)`: Minimal wrapper around Naas HTTP API.
  - `create_registry(name: str)`: Creates a registry; on HTTP `409` returns existing registry via `get_registry`.
  - `get_registry(name: str)`: Fetches registry details.
  - `get_registry_credentials(name: str)`: Fetches Docker registry credentials.
  - `create_space(space: Space)`: Creates a space; on HTTP `409` updates it; on HTTP `402` raises a `click.ClickException`.
  - `update_space(space: Space)`: Updates a space.
  - `get_space(name: str)`: Fetches space details.
- `NaasDeployer(configuration: EngineConfiguration)`: Orchestrates Docker build/push + Space creation.
  - `docker_build(image_name: str)`: Runs `docker build -t <image> . --platform linux/amd64`.
  - `deploy()`: Creates/gets registry, builds and pushes image, resolves image digest, creates/updates Space, prints success info.
- `_get_configuration(env: str)`: Sets `ENV` env var and loads `EngineConfiguration`; fails if deploy config is missing.

## Configuration/Dependencies

### Configuration
- Uses `EngineConfiguration.load_configuration()` after setting environment variable `ENV=<env>`.
- Requires `configuration.deploy` to be present (otherwise raises `click.ClickException`).
- Expected deploy-related values used:
  - `configuration.deploy.naas_api_key`
  - `configuration.deploy.space_name`
  - `configuration.deploy.env` (passed as container environment variables)

### External dependencies
- Docker CLI (`docker build`, `docker login`, `docker push`, `docker inspect`)
- Docker Compose CLI (`docker compose ...`)
- Network access to `https://api.naas.ai` (via `requests`)
- Python packages: `click`, `requests`, `pydantic`, `rich`, `naas_abi_core`

## Usage

### CLI
```bash
# Deploy to naas.ai using configuration selected by ENV=prod (default)
naas-abi-cli deploy naas --env prod

# Setup local deployment assets in current directory
naas-abi-cli deploy local --env local

# Bring local stack up (foreground)
naas-abi-cli deploy local-up

# Bring local stack up (detached)
naas-abi-cli deploy local-up --detach

# Tail logs
naas-abi-cli deploy local-logs

# Tear down (optionally remove volumes)
naas-abi-cli deploy local-down --volumes
```

### Programmatic (minimal)
```python
from naas_abi_cli.cli.deploy.deploy import _get_configuration, NaasDeployer

cfg = _get_configuration("prod")
NaasDeployer(cfg).deploy()
```

## Caveats
- Docker commands are executed via `subprocess.run(..., shell=True)` and their return codes are not checked.
- Image digest retrieval relies on `docker inspect --format='{{index .RepoDigests 0}}' ...`; if it returns empty, deployment aborts with a `click.ClickException`.
- `deploy local --env ...` ignores the `env` value and always calls `setup_local_deploy(os.getcwd())`.
- The container spec is hard-coded to:
  - container name: `api`
  - port: `9879`
  - cpu: `1`
  - memory: `1Gi`
