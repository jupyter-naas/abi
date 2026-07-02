# naas-abi-cli

Command Line Interface (CLI) tool for building and managing ABI (Agentic Brain Infrastructure) projects.

## Overview

`naas-abi-cli` provides a comprehensive set of commands to create, configure, deploy, and interact with ABI projects. It serves as the primary entry point for developers working with the ABI framework, enabling quick project setup, agent interaction, and cloud deployment.

## Installation

Install the CLI tool using pip:

```bash
pip install naas-abi-cli
```

## Available Commands

### Project Management

#### `abi new project <project-name> [project-path] [--with-local-deploy/--without-local-deploy]`
Creates a new ABI project with all necessary starter files and dependencies.

**What it does:**
- Creates a new project directory (must be empty or non-existent)
- Generates project structure with configuration files, Docker setup, and Python package structure
- Generates local deployment scaffolding (`docker-compose.yml`, `.deploy/`, and local `.env` values) by default
- Automatically installs required dependencies (`naas-abi-core`, `naas-abi-marketplace`, `naas-abi`, and `naas-abi-cli`)
- Customizes project files with your project name

**Example:**
```bash
abi new project my-abi-project
abi new project my-abi-project --without-local-deploy
```

#### `abi init <path>`
Initializes a new ABI project in the specified directory.

**Example:**
```bash
abi init .
```

### Agent Interaction

#### `abi chat [module-name] [agent-name]`
Starts an interactive chat session with an AI agent.

**Parameters:**
- `module-name`: The module containing the agent (default: `naas_abi`)
- `agent-name`: The specific agent class to use (default: `AbiAgent`)

**What it does:**
- Loads the ABI engine and specified module
- Launches an interactive terminal chat interface
- Saves conversations to `storage/datastore/interfaces/terminal_agent/`

**Example:**
```bash
abi chat naas_abi AbiAgent
```

#### `abi agent list`
Lists all available agents across all loaded modules.

**What it does:**
- Loads the ABI engine with all configured modules
- Displays a formatted table showing module names and agent class names

**Example:**
```bash
abi agent list
```

### Configuration Management

#### `abi config validate [--configuration-file <path>]`
Validates the ABI configuration file for correctness.

**Options:**
- `--configuration-file`: Path to configuration file (default: uses `config.yaml` from current directory)

**Example:**
```bash
abi config validate
abi config validate --configuration-file config.prod.yaml
```

#### `abi config render [--configuration-file <path>]`
Renders the loaded configuration as YAML output, useful for debugging and verification.

**Options:**
- `--configuration-file`: Path to configuration file (default: uses `config.yaml` from current directory)

**Example:**
```bash
abi config render
```

#### `abi module list`
Lists all available modules and their enabled/disabled status.

**What it does:**
- Loads the engine configuration
- Displays a formatted table showing module names and their enabled status

**Example:**
```bash
abi module list
```

### Deployment

#### `abi deploy naas [-e/--env <environment>]`
Deploys your ABI project to Naas cloud infrastructure.

**Options:**
- `-e, --env`: Environment to use (default: `prod`). Determines which configuration file to load (e.g., `config.prod.yaml`, `config.yaml`)

**What it does:**
- Builds a Docker image of your ABI project
- Pushes the image to your Naas container registry
- Creates or updates a space on Naas infrastructure
- Exposes your ABI REST API at `https://{space-name}.default.space.naas.ai`

**Requirements:**
- Naas API key configured in your configuration file
- Docker installed and running
- Deploy section in your `config.yaml` file

**Example:**
```bash
abi deploy naas
abi deploy naas --env prod
```

### Stack Management

Commands for the local Docker Compose stack (`config.local.yaml`). `abi start`,
`abi stop`, and `abi logs` are also exposed at the top level for convenience.

#### `abi stack snapshot create [-m/--note <text>] [--name <label>]`
Takes a point-in-time snapshot of the stack's stateful data so you can roll back
later or move the deployment to another host.

**What it does:**
- Resolves the compose project and its stateful volumes (`postgres_data`,
  `minio_data`, `fuseki_data`, `qdrant_storage`, `redis_data`, `rabbitmq_data`,
  `headscale_data`); transient volumes (caddy certs, dagster history, caches,
  the headscale socket dir) are skipped
- Gracefully stops the stack so the copy is consistent, archives each volume plus
  the host `storage/` directory, writes a `manifest.json` (timestamp, git commit,
  config fingerprints), then restarts the stack

> RabbitMQ note: durable queues only survive a restore if the broker's node name
> is stable. The compose file pins `hostname: rabbitmq` for this reason.
- Stores everything under `./.snapshots/<id>/` (gitignored)

**Example:**
```bash
abi stack snapshot create -m "before v3.15 upgrade"
```

#### `abi stack snapshot list`
Lists snapshots (newest first) with id, date, size, git commit, and note.

#### `abi stack snapshot restore <id> [--yes] [--no-safety-snapshot]`
Rolls the stack back to a snapshot. **Destructive** — it overwrites current data.

**What it does:**
- Validates the snapshot is complete *before* touching anything, so a corrupt or
  partial snapshot aborts without wiping any live data
- Warns if the git commit or `config.local.yaml`/`.env` have changed since capture
- Takes an automatic safety snapshot of the current state first (opt out with
  `--no-safety-snapshot`; skipped automatically on a fresh host with no data yet),
  so a rollback is itself reversible
- Stops the stack, restores the volumes + `storage/`, and brings it back up — and
  if anything fails mid-restore it still brings the stack back up and prints the
  safety-snapshot id to recover from

**Example:**
```bash
abi stack snapshot restore 20260630-140509
```

#### `abi stack snapshot delete <id> [--yes]` / `abi stack snapshot prune [--keep N] [--yes]`
Remove a single snapshot, or keep only the newest `N` (default 5).

#### `abi stack snapshot export <id> <archive.tar.gz>` / `abi stack snapshot import <archive.tar.gz>`
Bundle a snapshot into one portable archive and re-register it on another host —
the supported way to migrate a local deployment to a new machine:

```bash
# On the source host
abi stack snapshot create -m "migration"
abi stack snapshot export 20260630-140509 abi-migration.tar.gz
# copy abi-migration.tar.gz (and your .env) to the new host, then:
abi stack snapshot import abi-migration.tar.gz
abi stack snapshot restore 20260630-140509
```

`export` refuses to overwrite an existing file and `import` refuses to clobber a
snapshot with the same id; pass `--force` to either to override. `import` also
verifies the archive is complete (all volume tarballs + storage present) and
rejects a partial one.

> Note: the same `.env` (Postgres/MinIO/Fuseki credentials) must be present on the
> destination host — those credentials are baked into the data being restored.

### Secret Management

#### `abi secrets naas list`
Lists all secrets stored in your Naas workspace.

**Options:**
- `--naas-api-key`: Naas API key (default: `NAAS_API_KEY` environment variable)
- `--naas-api-url`: Naas API URL (default: `https://api.naas.ai`)

**Example:**
```bash
abi secrets naas list
```

#### `abi secrets naas push-env-as-base64`
Pushes a local `.env` file to Naas as a base64-encoded secret.

**Options:**
- `--naas-api-key`: Naas API key (default: `NAAS_API_KEY` environment variable)
- `--naas-api-url`: Naas API URL (default: `https://api.naas.ai`)
- `--naas-secret-name`: Name for the secret in Naas (default: `abi_secrets`)
- `--env-file`: Path to the environment file (default: `.env.prod`)

**Example:**
```bash
abi secrets naas push-env-as-base64 --env-file .env.prod
```

#### `abi secrets naas get-base64-env`
Retrieves a base64-encoded secret from Naas and displays it as environment variables.

**Options:**
- `--naas-api-key`: Naas API key (default: `NAAS_API_KEY` environment variable)
- `--naas-api-url`: Naas API URL (default: `https://api.naas.ai`)
- `--naas-secret-name`: Name of the secret to retrieve (default: `abi_secrets`)

**Example:**
```bash
abi secrets naas get-base64-env
```

### Script Execution

#### `abi run script <path>`
Runs a Python script in the context of a loaded ABI engine.

**What it does:**
- Loads the ABI engine with all configured modules
- Executes the specified Python script with access to the engine and all loaded modules

**Example:**
```bash
abi run script scripts/my_script.py
```

## Architecture

The CLI is built using:
- **Click**: For command-line interface framework
- **naas-abi-core**: Core ABI engine and configuration management
- **naas-abi-marketplace**: Marketplace modules and agents
- **naas-abi**: Main ABI package

When run inside an ABI project, the CLI auto-detects the project root and re-runs itself in that project context via `uv run --project ...`.

## Project Structure

When you create a new project with `abi new project`, the CLI:
1. Uses template files from `cli/new/templates/project/`
2. Customizes templates with your project name
3. Sets up proper Python package structure
4. Sets up local deployment files from `cli/deploy/templates/local/` (unless disabled)
5. Installs all required dependencies via `uv`

## Integration with ABI Framework

The CLI integrates seamlessly with the ABI ecosystem:
- **Engine Loading**: Automatically loads modules and agents from your configuration
- **Configuration Management**: Validates and renders YAML configuration files
- **Cloud Deployment**: Handles Docker builds and Naas API interactions
- **Secret Management**: Integrates with Naas secret storage for secure credential management

## Dependencies

- Python 3.10+
- `naas-abi>=1.0.6`
- `naas-abi-core[qdrant]>=1.1.2`
- `naas-abi-marketplace[ai-chatgpt]>=1.1.0`
- `uv` package manager (for dependency management)

## See Also

- [ABI Main README](../../../README.md) - Complete ABI framework documentation
- [naas-abi-core](../naas-abi-core/) - Core engine documentation
- [naas-abi-marketplace](../naas-abi-marketplace/) - Marketplace modules documentation
