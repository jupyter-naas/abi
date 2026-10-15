# naas-abi-cli

Command Line Interface (CLI) tool for building and managing ABI (Agentic Brain Infrastructure) projects.

## Overview

`naas-abi-cli` provides a comprehensive set of commands to create, configure, deploy, and interact with ABI projects. It serves as the primary entry point for developers working with the ABI framework, enabling quick project setup, agent interaction, and cloud deployment.

Since 3.0, `abi new project` creates projects that run on NATS and `abi new
module` creates remote modules (`naas-abi-sdk`). Dagster and RabbitMQ are
legacy extras for projects without NATS, removed in the next major. Upgrading
a 2.x project: [Migrate from 2.x to 3.0](https://github.com/jupyter-naas/abi/blob/main/docs/site/docs/upgrade/migrate-to-3.md).
Every command: [CLI Reference](https://github.com/jupyter-naas/abi/blob/main/docs/site/docs/capabilities/developer-toolchain/cli.md).

## Installation

Install the CLI tool using pip:

```bash
pip install naas-abi-cli
```

## Available Commands

### Project Management

#### `abi new project <project-name> [project-path] [--with-local-deploy/--without-local-deploy] [--without-nats]`
Creates a new ABI project with all necessary starter files and dependencies.

**What it does:**
- Creates a new project directory (must be empty or non-existent)
- Generates project structure with configuration files, Docker setup, and Python package structure
- Generates local deployment scaffolding (`docker-compose.yml`, `.deploy/`, and local `.env` values) by default
- Automatically installs required dependencies (`naas-abi-core`, `naas-abi-marketplace`, `naas-abi`, and `naas-abi-cli`; `naas-abi-sdk` and `naas-abi-proto` in NATS mode)
- Customizes project files with your project name

**NATS by default.** The project runs the engine on NATS: every config has a
`nats:` block with discovery on (project = the project name), the bus is
JetStream, and `.env` holds `NATS_JWT_SECRET` and the broker passwords
(`NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD`). The Docker stack starts the
`nats` service, keeps RabbitMQ behind the `rabbitmq` profile and runs no
Dagster: one engine hosts discovery, and module jobs replace Dagster's
schedules. Check the broker with `curl -s localhost:8222/healthz` and
`curl -s localhost:8222/connz`.

NATS mode installs `naas-abi-proto` and `naas-abi-sdk` from the `.abi`
submodule (they are not on PyPI yet), so it refuses `--without-abi-submodule`.
`--without-nats` creates the classic in-process project (RabbitMQ in Docker,
no broker for `abi dev`). The project's own module (`src/<project>/`, holding
the default agent) is an in-engine module either way.

**Example:**
```bash
abi new project my-abi-project
abi new project my-abi-project --without-local-deploy
abi new project my-abi-project --without-nats   # classic, in-process
```

#### `abi new module <name> [path] [--in-engine | --remote] [--standalone] [--abi-ref <ref>]`
Creates a module. By default a **remote module**: a `naas-abi-sdk` package that
runs in its own process, reaches the engine only through NATS, and never
imports `naas_abi_core`. It has an agent (an SDK `IntentAgent` on the engine's
default models, its memory in the Document Service), an hourly `@job`, a
`python -m <name>` entrypoint with discovery and SIGTERM handling (it signs
its tokens with its module key, `ABI_MODULE_KEY`), an app scaffold and offline
tests.

- **In a project** (a folder with `config.yaml` and `pyproject.toml`), it goes
  to `src/<name>/` with an SDK-only `Dockerfile`, gets a `dev.modules` entry in
  `config.yaml` (`abi dev up` runs it) and a service in
  `docker-compose.override.yml` (`abi start` runs it; `abi deploy local
  --regenerate` never touches that file), with its module key in `.env`
  (`ABI_MODULE_KEY_<NAME>`). It is not added to `modules:`: it
  registers itself through discovery, and Nexus lists its agent once the
  module logs `READY`.
- **`--standalone`** (the default outside a project) creates a repository of
  its own: `pyproject.toml` (`naas-abi-sdk[agent,otel]` and `naas-abi-proto`
  from git at `--abi-ref`, by default this CLI's release tag
  `naas-abi-cli-v<version>`, so they match the CLI and never move),
  `Dockerfile`, `README.md`, `AGENTS.md`, ready for `git init`.
- **`--in-engine`** (alias `--local`) creates the classic module the engine
  loads (agents, integrations, pipelines, workflows, orchestrations,
  ontologies); add it under `modules:`. It is the default in a project whose
  config has no `nats:` block, where nothing would run a remote module;
  **`--remote`** creates a remote one there anyway, ready for when the
  project moves to NATS.

Inside a remote module, `abi new agent` writes an SDK agent and `abi new app`
adds an app the module serves through Nexus, with an optional backend
(`self.expose_app(name, asgi_app)`); `abi new workflow`,
`pipeline`, `integration` and `orchestration` scaffold core code, so they
refuse and say what to use instead.

**Example:**
```bash
abi new module research                 # remote, in a NATS project
abi new module research --standalone    # its own repository
abi new module legacy --in-engine       # loaded by the engine
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

#### `abi agent migrate-memory [--from postgres|documents-v1] [--thread <id>]... [--apply]`
Copies agent memory into the Document Service (checkpoint schema 2), from
LangGraph's PostgreSQL tables (`--source-url`, default `$POSTGRES_URL`) or from
document schema 1. A dry run unless `--apply`; running it again copies only
what is missing. Stop the engines first. In NATS mode the engine runs the same
copy as the `agent_memory_migrate` job.

#### `abi agent prune-memory [--keep-last N] [--min-age S] [--thread <id>]... [--apply]`
Deletes old checkpoints, keeping each thread's newest `--keep-last` (default
20); the conversation stays whole in them. A dry run unless `--apply`. In NATS
mode the engine runs it daily as the `agent_memory_prune` job.

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

#### `abi module key <module_id>`
Prints the module key of `<module_id>`, derived from the project's
`NATS_JWT_SECRET` (`$NATS_JWT_SECRET`, else `./.env`). A remote module signs its
tokens with it (`ABI_MODULE_KEY`), and the engine accepts them for that module
id only, never for `api`, `engine` or `dagster`. Discovery registers a module
only under a token for its own module id. Give a module its key, never the
secret; a new secret means new keys.

### Local dev stack

#### `abi dev up [--service <name>]... [-d] [--with-nats/--without-nats] [--with-tracing]`
Runs the stack natively (no Docker). When the project config has a `nats:` block, the engine runs in NATS mode: oxigraph, nats, api, nexus-web, then the `dev.modules`. Dagster is left out (module jobs replace it). It needs `nats-server` 2.14 or later on `PATH` and fails with an install hint without it (or with an older one), rather than falling back to in-process mode. A project without a `nats:` block runs in-process with oxigraph, api, dagster and nexus-web. `--with-nats` and `--without-nats` choose the mode whatever the config says; `--without-nats` on a NATS project writes an overlay that sets `nats: null`. `--with-tracing` adds Jaeger. `abi dev down`, `abi dev status`, `abi dev logs <name> [-f]` manage it; pids and logs live in `.abi/dev/`. The discovery project is the config's `nats.discovery.project`, else the folder name.

In NATS mode, the SDK modules listed under `dev.modules` in the project config (`abi new module` adds them) start once the api is ready, each under a supervisor that restarts it when it exits on its own (backing off from 1 s to 30 s):

```yaml
dev:
  modules:
    - name: probe-researcher                # logs, pid, --service name
      module: operations.projects.nats_probe  # run as `python -m <module> <args>`
      identity: operations.projects.nats_probe.researcher  # its module id (default: its ABIModule's)
      args: [researcher]
      env: {NATS_PROBE_DISCOVERY_PROJECT: "${ABI_DISCOVERY_PROJECT}"}
      restart: on-failure                   # or always, never
```

Each module gets `ABI_NATS_URL`, `ABI_MODULE_KEY` (the key of its module id, which discovery registers it under: its `identity:`, else the `module_id` of the `ABIModule` its package exports; `abi dev up` refuses a module whose id it cannot tell), `ABI_SERVICE_TOKEN` signed with that key (for modules that read only that; the SDK prefers the key), `ABI_DISCOVERY_PROJECT`, `OTEL_EXPORTER_OTLP_ENDPOINT` with tracing, and the project's `src/` on `PYTHONPATH`; `env` values may name them as `${VAR}`. A module is addressed like a service: `abi dev up --service probe-researcher -d` (it joins the running NATS stack and starts no broker of its own), `abi dev logs probe-researcher -f`, `abi dev down --service probe-researcher`. `abi dev down` stops modules before the stack. The engine validates the block and otherwise ignores it.

### Deployment

#### `abi deploy local [--regenerate] [--no-backup] [--headscale] [--coding]`
Writes the project's Docker Compose stack (`docker-compose.yml`, `.deploy/`).
`--regenerate` re-renders it from the current templates, after a backup.

- A project with a `nats:` block gets the NATS stack: a `nats` service the
  engine waits for, no Dagster, RabbitMQ behind the `rabbitmq` profile.
- A project without one keeps the classic stack (Dagster and RabbitMQ, legacy)
  with a `nats` service behind the `nats` profile, and `uv add`s the
  `naas-abi-core[dagster,rabbitmq]` extras it needs (commit `pyproject.toml`
  and `uv.lock`).
- It writes `.deploy/docker/nats/nats.conf` (the broker users `abi` and
  `module`, and the module user's permissions) and generates
  `NATS_ABI_PASSWORD` and `NATS_MODULE_PASSWORD` in `.env`. Regenerate after
  each CLI upgrade.
- It stops before writing anything when `.env` is not writable, and prints the
  `chown` to run.
- `docker-compose.override.yml` (remote modules) is never rewritten.

`abi deploy local-up [-d]`, `local-down` and `local-logs` run Docker Compose
with the override file.

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
Rolls the stack back to a snapshot. **Destructive**: it overwrites current data.

**What it does:**
- Validates the snapshot is complete *before* touching anything, so a corrupt or
  partial snapshot aborts without wiping any live data
- Warns if the git commit or `config.local.yaml`/`.env` have changed since capture
- Takes an automatic safety snapshot of the current state first (opt out with
  `--no-safety-snapshot`; skipped automatically on a fresh host with no data yet),
  so a rollback is itself reversible
- Stops the stack, restores the volumes + `storage/`, and brings it back up, and
  if anything fails mid-restore it still brings the stack back up and prints the
  safety-snapshot id to recover from

**Example:**
```bash
abi stack snapshot restore 20260630-140509
```

#### `abi stack snapshot delete <id> [--yes]` / `abi stack snapshot prune [--keep N] [--yes]`
Remove a single snapshot, or keep only the newest `N` (default 5).

#### `abi stack snapshot export <id> <archive.tar.gz>` / `abi stack snapshot import <archive.tar.gz>`
Bundle a snapshot into one portable archive and re-register it on another host :
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
> destination host : those credentials are baked into the data being restored.

### Nexus admin (workspace / user / org)

Authenticated admin surface against the Nexus HTTP API. Auth via
`NEXUS_ACCESS_TOKEN`, or `NEXUS_EMAIL` + `NEXUS_PASSWORD`. Base URL:
`NEXUS_API_URL` (default `http://localhost:9879`).

```bash
abi workspace create --name "Research preview" --slug research-preview --org org-...
abi workspace list --org org-...
abi workspace members list --workspace ws-...
abi workspace members add --workspace ws-... --email someone@naas.ai --role member

# Preferred when password signup is off: create-on-invite + OTP/magic-link email
abi user invite --email someone@gmail.com --name "Someone" \
  --org org-... --workspace ws-... --role member --workspace-role member
abi org members invite --org org-... --email someone@gmail.com --workspace ws-...

abi user create --email someone@naas.ai --name "Someone"   # needs password auth enabled
abi user list --org org-...   # or --workspace ws-...

abi org list
abi org members list --org org-...
abi org workspaces --org org-...
```

All of these accept `--dry-run` (prints the intended API call) and
`--api-url` / `--token` / `--auth-email` / `--auth-password`.

Invite endpoints create the user when missing and email OTP / magic-link sign-in.

**Credentials:** `abi user create` never prints the password by default. It
writes `secrets/NEXUS_USER_<EMAIL>.env` (mode 600). Pass `--show-password` only
when you intentionally need stdout.

**Break-glass Postgres** (ops VM only, when invite email / browser auth is
unavailable):

```bash
export NEXUS_POSTGRES_COMPOSE_DIR=/opt/abi
abi user create --via postgres --email someone@naas.ai --name "Someone" --org org-...
abi workspace create --via postgres --name "..." --slug ... --org org-... --owner-id user-...
```

See issue [#1118](https://github.com/jupyter-naas/abi/issues/1118).

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

- [ABI Main README](https://github.com/jupyter-naas/abi/blob/main/README.md) - Complete ABI framework documentation
- [naas-abi-core](https://github.com/jupyter-naas/abi/tree/main/libs/naas-abi-core) - Core engine documentation
- [naas-abi-marketplace](https://github.com/jupyter-naas/abi/tree/main/libs/naas-abi-marketplace) - Marketplace modules documentation
