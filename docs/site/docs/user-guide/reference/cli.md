# CLI Reference

The `abi` CLI (`naas-abi-cli`) creates projects and modules, runs them natively or with Docker, and manages the stack. Run `abi <command> --help` for every option. Inside a project, `abi` re-runs itself with the project's own version (it says so on stderr).

---

## Installation

```bash
uv tool install naas-abi-cli --force --upgrade --with-executables-from naas-abi-core
abi --help
```

---

## abi new

Scaffold a project, or a part of one.

```bash
abi new project my_ai                     # a NATS project (the default since 3.0)
abi new project my_ai --without-nats      # the classic in-process project (Dagster, RabbitMQ: legacy)
abi new project my_ai --without-local-deploy
abi new project my_ai --domain example.com

abi new module research                   # a remote module (SDK) in a NATS project
abi new module legacy --in-engine         # a module the engine loads (alias --local)
abi new module research --remote          # a remote module in a project without NATS
abi new module research --standalone      # a remote module in a repository of its own
```

- `abi new project` adds ABI as the `.abi` git submodule (a NATS project needs it until `naas-abi-proto` and `naas-abi-sdk` are on PyPI; `--without-abi-submodule` is refused with NATS), writes the configs with a `nats:` block, the Docker Compose stack, and `.env` with `NATS_JWT_SECRET`, `NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD` and the admin's password.
- `abi new module` in a NATS project (a `nats:` block in `config.yaml` or `config.local.yaml`), or outside any project, creates a remote module: in a project, `src/<name>/` with a `dev.modules` entry, a service in `docker-compose.override.yml` and its key in `.env` (`ABI_MODULE_KEY_<NAME>`). In a project without a `nats:` block it creates an in-engine module and says so. `--standalone` pins the SDK to the CLI's release tag (`--abi-ref` picks another).
- Inside a remote module, `abi new agent <Name> agents` writes an SDK agent and `abi new app <name> apps` an app; `abi new workflow`, `pipeline`, `integration` and `orchestration` refuse (they write `naas_abi_core` code).
- In an in-engine module: `abi new agent`, `workflow`, `pipeline`, `integration`, `app`. `abi new orchestration` writes a Dagster orchestration, for a project without NATS only (legacy).

See [Build a Remote Module](/user-guide/build/sdk/build-a-remote-module).

---

## abi dev

Run the project natively, without Docker.

```bash
abi dev up                       # foreground; Ctrl+C stops everything
abi dev up -d                    # in the background
abi dev up --with-tracing        # also run Jaeger v2 and export traces
abi dev up --with-nats           # force NATS mode (default with a `nats:` block)
abi dev up --without-nats        # force in-process mode
abi dev up --service api -d      # one service or dev module (repeatable)
abi dev up --log-level INFO      # the API logs at DEBUG by default
abi dev status                   # services, dev modules, pids and health
abi dev ports                    # the ports of this checkout
abi dev logs research -f         # a service's or dev module's log
abi dev down                     # stop (dev modules first)
abi dev down --service research  # stop one
abi dev nuke                     # wipe local state (storage/, logs); keeps .env
```

- **NATS mode** (a `nats:` block in the config): `nats-server` (2.14 or later, on `PATH`), Oxigraph, the API with discovery and jobs, Nexus web, then every `dev.modules` entry. It writes the broker's config with the users `abi` and `module`, the NATS keys in `.env` when missing, and `.abi/dev/dev.overlay.yaml`, which points the engine at its broker; `config.yaml` stays untouched. Dagster is left out.
- **In-process mode** (no `nats:` block): Oxigraph, the API, Dagster (only when the project installs the legacy `naas-abi-core[dagster]` extra; it says so otherwise) and Nexus web.
- **Dev modules** (`dev.modules` in the config) each run as `python -m <module>` under a supervisor that restarts them, with `ABI_NATS_URL`, `ABI_MODULE_KEY` (the key of the entry's module id), `ABI_DISCOVERY_PROJECT` and, with tracing, `OTEL_EXPORTER_OTLP_ENDPOINT`.
- Each git worktree gets its own ports.

---

## abi deploy

```bash
abi deploy local                 # write the Docker Compose stack
abi deploy local --regenerate    # re-render it from the current templates (backs up first)
abi deploy local-up -d           # docker compose up, with docker-compose.override.yml
abi deploy local-logs
abi deploy local-down
```

- A project with a `nats:` block gets the NATS stack: a `nats` service the engine waits for, no Dagster, RabbitMQ behind the profile `rabbitmq`.
- A project without one keeps the classic stack (Dagster, RabbitMQ: legacy), with a `nats` service behind the profile `nats`, and gets the `naas-abi-core[dagster,rabbitmq]` extras added to its `pyproject.toml` (`uv add`; commit the change).
- It writes `.deploy/docker/nats/nats.conf` (the broker's users and the `module` user's permissions) and the broker's passwords in `.env`. Regenerate after each CLI upgrade.
- `--regenerate` never touches `docker-compose.override.yml`, where remote modules live.

---

## abi stack

Manage the Docker stack.

```bash
abi stack start                  # start, and wait until services are ready
abi stack status                 # readiness per service (TCP/HTTP probes)
abi stack logs api               # logs of one service
abi stack stop
abi stack tui                    # interactive terminal UI
abi stack snapshot create -m "before upgrade"
abi stack snapshot list
abi stack snapshot restore <id>  # destructive
```

A snapshot archives the data volumes and `storage/`, not the `nats_data` volume. `abi start` and `abi stop` are shortcuts for the stack.

---

## abi module

```bash
abi module key my_ai.research    # print a remote module's key (ABI_MODULE_KEY)
abi module list                  # the modules in the config, and whether they are enabled
```

`abi module key` derives the key from the project's `NATS_JWT_SECRET` (`$NATS_JWT_SECRET`, else `./.env`). The key signs tokens for that module id only; a module never gets the secret itself. A new secret means new keys.

---

## abi agent

```bash
abi agent list                                   # agents the engine loads
abi agent migrate-memory                         # dry run: PostgreSQL memory → Document Service
abi agent migrate-memory --apply
abi agent migrate-memory --from documents-v1     # from document schema 1
abi agent prune-memory --keep-last 20            # dry run
abi agent prune-memory --keep-last 20 --apply
```

Stop the engines (API, Dagster) before `migrate-memory` or `prune-memory`. In NATS mode, the engine runs the same work as jobs: `agent_memory_migrate` (on demand, from the System app) and `agent_memory_prune` (daily). See [Migrate from 2.x to 3.0](/user-guide/upgrade/migrate-to-3#right-after-the-restart-copy-agent-memory-and-activity-logs).

---

## abi chat, abi run

```bash
abi chat                         # the default agent
abi chat naas_abi AbiAgent       # an agent, by module and name
abi run script path/to/script.py
```

They load an engine with `ABI_ENGINE_ROLE=auto`: it serves when no engine runs, and is a NATS client of the running one otherwise.

---

## abi config, abi docs

```bash
abi config validate              # load and validate the project's config
abi config render                # print it rendered
abi docs sync --fail-on-stale    # reference pages older than their source
```

---

## Makefile targets (repository)

The ABI repository's `Makefile` has lower-level targets, useful in CI:

```bash
make api                   # Start the API dev server (port 9879)
make mcp                   # Start the MCP server (STDIO)
make mcp-http              # Start the MCP server (SSE, port 8000)
make sparql-terminal       # Interactive SPARQL query terminal
make test                  # Run all tests
make check                 # Linting and type checks
make docs                  # Serve this documentation site locally
```
