# AGENTS.md

Guidance for coding agents in `/Users/XXXX/abi`.

## Repo Overview

- Python monorepo managed with `uv`.
- Main packages: `libs/naas-abi-core`, `libs/naas-abi`, `libs/naas-abi-cli`, `libs/naas-abi-marketplace`.
- Root project links local packages via editable `tool.uv.sources` in `pyproject.toml`.
- Python target is `>=3.10,<4`.
- Frontend: Next.js app at `libs/naas-abi/naas_abi/apps/nexus/apps/web` (requires `pnpm`).

## Navigating the Codebase (read this first)

**Before working in any service or domain, read the nearest `AGENTS.md`.** Each one is the canonical reference for that scope — port interface, public API, adapters, factory, test commands, and how to add a new adapter. They are kept up to date in-tree and supersede any external documentation.

Discovery rule:

1. Find the closest `AGENTS.md` walking up from your working file.
2. If none exists for the scope you're modifying, create one following the structure of the service files below.

## Service Map

Core services live under `libs/naas-abi-core/naas_abi_core/services/`. Each has its own `AGENTS.md`:

| Service | What it does | AGENTS.md |
|---|---|---|
| `activity_log` | Per-actor activity event log (fail-open recording) | [services/activity_log/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/activity_log/AGENTS.md) |
| `agent` | LLM ↔ tools/sub-agents orchestration, memory, SSE streaming | [services/agent/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/agent/AGENTS.md) |
| `agent_composer` | Build agents from records (`AgentSpec`, kept in the Document Service, files or memory) or programmatically | [services/agent_composer/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/agent_composer/AGENTS.md) |
| `bus` | Pub/sub + durable work-queue message broker | [services/bus/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/bus/AGENTS.md) |
| `cache` | Multi-tier (hot/cold) cache with decorator API | [services/cache/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/cache/AGENTS.md) |
| `document` | Portable mutable documents, scoped to modules (SQLite / PostgreSQL) | [services/document/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/document/AGENTS.md) |
| `email` | Transactional email sending (SMTP / SES / FS) | [services/email/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/email/AGENTS.md) |
| `event` | Durable typed event log + live pub/sub | [services/event/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/event/AGENTS.md) |
| `keyvalue` | Bytes-in/out KV store with TTL + atomic CAS/CAD | [services/keyvalue/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/keyvalue/AGENTS.md) |
| `model_registry` | Canonical-ID catalog of chat/embedding models | [services/model_registry/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/model_registry/AGENTS.md) |
| `object_storage` | S3-style blob storage (FS / S3 / Naas) | [services/object_storage/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/object_storage/AGENTS.md) |
| `ontology` | LLM-powered NER against an RDF/OWL ontology | [services/ontology/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/ontology/AGENTS.md) |
| `secret` | Layered secret store (dotenv / Naas / base64); over NATS the engine's own processes see every secret, an SDK module only the names `nats.secret.modules.<id>` grants it (denied by default) | [services/secret/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/secret/AGENTS.md) |
| `tool_registry` | Catalog of module tools, one per process (also with NATS): versioned ids, bindings, semantic search; its catalog is served over NATS (`abi.svc.tool_registry.v1`: list, get, search read only) to client engines and SDK modules, which can also run an engine tool there (`invoke_tool`: the engine resolves config and secrets and enforces access from the caller's verified identity, denied by default per module); tools SDK modules serve (`tools = (ToolDescriptor(...),)`) join it through discovery and run over NATS (`abi.tool.v1`), with no engine secret sent to the module | [services/tool_registry/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/tool_registry/AGENTS.md) |
| `triple_store` | RDF/SPARQL named-graph store + view subscriptions | [services/triple_store/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/triple_store/AGENTS.md) |
| `vector_store` | Vector DB facade (Qdrant / SQLite-vec) | [services/vector_store/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/vector_store/AGENTS.md) |

Every service AGENTS.md follows the same structure: **Purpose → Files → Port → Service API → Adapters → Factory → Tests → Adding a new adapter** — so once you've read one, you know how to navigate them all.

## Marketplace Map

The marketplace (`libs/naas-abi-marketplace/`) is a registry of pluggable modules — LLM providers, third-party integrations, and domain expert agents — that extend core. Read its master guide before working in any subdirectory:

| Scope | What's there | AGENTS.md |
|---|---|---|
| Marketplace overview | Module shape, categories, config, discovery cheat sheet, how to add a module | [libs/naas-abi-marketplace/AGENTS.md](libs/naas-abi-marketplace/AGENTS.md) |
| AI provider modules | Claude, ChatGPT, Gemini, Grok, Mistral, Llama, Qwen, DeepSeek, Gemma, Perplexity, Bedrock | `libs/naas-abi-marketplace/naas_abi_marketplace/ai/` |
| Application integrations | GitHub, LinkedIn, Postgres, Notion, Salesforce, Slack, … (47 apps) | `libs/naas-abi-marketplace/naas_abi_marketplace/applications/` |
| Domain expert agents | Software Engineer, Accountant, DevOps, Data Engineer, … (24 roles) | `libs/naas-abi-marketplace/naas_abi_marketplace/domains/` |
| Reference scaffolds | Demo agents, workflows, Streamlit apps, Dagster orchestration | `libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/` |

## Extra Rules Discovery

- Checked `.github/copilot-instructions.md`: not present.
- Additional instructions are defined in `~/.claude/CLAUDE.md`:
  - Use `gh` CLI for GitHub operations.
  - Follow Hexagonal Architecture.
  - Keep business logic technology-agnostic.
  - Organize as self-sufficient domains with ports/adapters/factories.
  - Prefer TDD (tests first).

## Setup Commands

Run from repository root unless noted.

### First-Time Setup (CRITICAL)

```bash
# 1. Python dependencies
uv sync --all-extras

# 2. Install missing Python deps (greenlet required for asyncpg)
uv pip install greenlet

# 3. Frontend dependencies
cd libs/naas-abi/naas_abi/apps/nexus/apps/web
pnpm install
cd ../../../../..

# 4. Configure for local development
# Edit .env and change Docker hostnames to localhost:
#   POSTGRES_HOST=localhost (not postgres)
#   QDRANT_HOST=localhost (not qdrant)
#   MINIO_HOST=localhost (not minio)
#   RABBITMQ_HOST=localhost (legacy RabbitMQ bus only)

# 5. NATS: the repo runs on it by default. `abi dev up` needs nats-server 2.14+
#    on PATH (https://github.com/nats-io/nats-server/releases); `abi stack start`
#    runs it in Docker. Both generate its secrets into .env.
```

Alternative bootstrap:

```bash
make deps
```

## Build Commands

```bash
# Python package build (hatchling)
uv build

# Build root Docker image
make build

# Build specific package project
uv build --project libs/naas-abi-core
```

## Lint, Format, Type Check

```bash
# Main quality gates
make check
make check-core
make check-marketplace

# Formatting
make fmt
# or
uvx ruff format

# Lint only
uvx ruff check libs/naas-abi-core libs/naas-abi libs/naas-abi-cli
uvx ruff check libs/naas-abi-marketplace
```

Direct mypy examples:

```bash
cd libs/naas-abi-core && uv sync --all-extras && .venv/bin/mypy -p naas_abi_core --follow-untyped-imports
cd libs/naas-abi-cli && uv sync --all-extras && .venv/bin/mypy -p naas_abi_cli --follow-untyped-imports
```

## Test Commands

```bash
# Full test run
make test
# equivalent
uv run python -m pytest .

# Package-scoped runs
uv run pytest libs/naas-abi-core
uv run pytest libs/naas-abi
uv run pytest libs/naas-abi-cli
uv run pytest libs/naas-abi-marketplace

# CLI end to end: new project, modules, `abi dev up`, checks, `abi dev down`
# (no Docker, no model). See libs/naas-abi-cli/AGENTS.md.
scripts/cli_smoke.sh [nats|without-nats]
```

Single-test execution (important):

```bash
# single file
uv run pytest libs/naas-abi-core/naas_abi_core/apps/api/api_test.py -v

# single class
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/adapters/secondary/PythonAdapter_test.py::TestPythonAdapter -v

# single test function
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/adapters/secondary/PythonAdapter_test.py::TestPythonAdapter::test_set_get_exists_delete -v

# keyword filtering
uv run pytest libs/naas-abi-core -k "postgres or checkpointer" -v
```

Notes:

- `pytest.ini` enables strict markers/config and coverage output.
- Test naming in this repo uses both `*_test.py` and `test_*.py`; follow nearby files.
- Test **placement** follows the scope of what is under test. Both forms are intentional —
  do not consolidate them:
  - **Beside its source** for a test covering one file: `users.py` → `users_test.py`.
    It is found where the code is, and moves with it when the code moves.
  - **In the module's `tests/`** for a test with no single natural neighbour — module-wide
    behaviour, or something defined in `__init__.py`. `tests/` also holds shared
    `artifacts/` fixtures. Example: `applications/x/tests/XTweetSearchWorkflowConfiguration_test.py`,
    which covers a config model declared in the module's `__init__.py`.

## Architecture Guidelines

- Keep strict Ports-and-Adapters boundaries.
- Domain logic must not depend on concrete infrastructure details.
- Preserve self-contained domain structure: interfaces, domain, primary adapters, secondary adapters, factories, tests.
- Reuse/add generic adapter tests for new adapters when relevant.
- Do not bypass architecture with direct infra calls from domain code.
- **All secondary adapters MUST implement ALL abstract methods from their port interface**, even if returning `NotImplementedError` for unsupported operations.

## Common Issues & Fixes

### Missing Abstract Methods in Adapters

**Problem:** `TypeError: Can't instantiate abstract class X with abstract methods Y`  
**Solution:** Implement all abstract methods from the port interface. For unsupported features, raise `NotImplementedError` with a clear message.

Example:

```python
def unsupported_method(self, arg: str) -> None:
    raise NotImplementedError("Feature not supported by this adapter")
```

### Local Development Environment Configuration

**Problem:** Services can't connect when running outside Docker  
**Solution:** `.env` file must use `localhost` for host services, not Docker service names:

- ✅ `POSTGRES_HOST=localhost`
- ❌ `POSTGRES_HOST=postgres`

**Problem:** Missing Python dependencies (e.g., `greenlet`)  
**Solution:** `uv pip install greenlet` (required for SQLAlchemy asyncpg)

**Problem:** Frontend won't start (`next: command not found`)  
**Solution:** Run `pnpm install` in `libs/naas-abi/naas_abi/apps/nexus/apps/web`

### Local Access

After `abi stack start`, the web UI is at `http://localhost:3042`.

There is no default password. The only seeded account is `admin@example.com`; its password is generated per project and stored in `.env` as `NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`:

```bash
grep NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD .env
```

Password login is enabled via `auth_password_enabled: true` in `config.local.yaml`. Set it to `false` to switch back to magic link.

Self-registration is off (`auth_signup_enabled: false`): add people by invitation or through `users:` in the config. Sign-in endpoints are rate limited in every environment (5 failures per account and 20 attempts per IP per 5 minutes); `rate_limit_enabled: false` turns this off for local debugging.

**How the password is set:** `abi new project`, `abi dev up` and `abi deploy local` generate it into `.env`. On first boot the seeder creates the account with that value; if the key is missing it generates one and writes it back. Published defaults (`admin`, `Admin1234!`) are never accepted: login refuses them, and on boot the seeder replaces them with a generated password written to `.env`.

If you see "Incorrect email or password", read the current value from `.env` (it may have just been rotated), or wipe and reseed when there is no data to keep:
```bash
docker volume rm abi_postgres_data
abi stack start
```

### Deploying with Dokploy

`abi deploy dokploy --domain <domain> [--coding] [--wildcard-cert-resolver <name>]` renders `docker-compose.dokploy.yml`, `config.dokploy.yaml` and a gitignored `.env.dokploy` for a Dokploy server: Traefik labels instead of Caddy, no host ports, `abi` built from the project `Dockerfile`. Code: `libs/naas-abi-cli/naas_abi_cli/cli/deploy/dokploy.py`, template in `deploy/templates/dokploy/`, tests in `deploy/dokploy_test.py`. Guide: `docs/site/docs/user-guide/deploy/dokploy.md`; decision: `docs/adr/20261013_dokploy-deployment.md`.

## Stack Management

The repo runs on NATS by default, like a project from `abi new project`: its
`config.yaml` (`abi dev up`) and `config.local.yaml` (`abi stack start`) have a
`nats:` block. Kernel services, the bus (JetStream), module jobs and remote
module discovery go through the broker. The broker's passwords
(`NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD`) and `NATS_JWT_SECRET` are generated
into `.env` on first run (see `.env.example`).

Dagster and the RabbitMQ bus are legacy, to be removed in the next major. In
`docker-compose.yml` they sit behind the `legacy` profile, and nothing in the
default stack depends on them.

```bash
# Start the Docker stack on NATS (Postgres, Fuseki, Qdrant, Redis, MinIO, NATS, ...)
abi stack start

# Legacy: also Dagster and RabbitMQ, the engine without NATS, its bus on RabbitMQ
# (writes .abi/stack/legacy.overlay.yaml for the abi and dagster containers)
abi stack start --legacy

# Start only infrastructure (Postgres + Fuseki + NATS). The nats service needs
# its passwords in .env: run `abi stack start` once, or `make local-up`.
docker compose up -d postgres fuseki nats

# Legacy containers alone, next to the engine on NATS (Dagster joins it as a client)
docker compose --profile legacy up -d dagster

# Check status
abi stack status

# View logs
abi stack logs          # All services
abi stack logs core     # Core API only
abi stack logs api      # Nexus API only
abi stack logs web      # Frontend only

# Stop services (the legacy profile's too)
abi stack stop
```

Without Docker, `abi dev up` runs the same engine on a native `nats-server`
(see "Hosted development environment instructions" below); `abi dev up
--without-nats` is the legacy in-process engine, with Dagster when the
`naas-abi-core[dagster]` extra is installed.

`abi chat`, `make api` and tests that build an `Engine()` from the root config
are on NATS too: they need a broker at `127.0.0.1:4222`, the Docker stack's. To
load the engine in-process without one, point `ABI_CONFIG_OVERLAY` at a YAML
file holding `nats: null`.

### Configuration Adapters

Services can be configured to use different adapters in `config.yaml`:

**NATS (`nats:` block):** with it, the bus is JetStream on the broker and needs
no `bus:` block (an explicit one must be `nats_jetstream`); other engines and
remote modules reach the kernel services over NATS. Without it, the engine runs
in-process and uses the `bus:` adapter below.

**Bus Service** (without NATS):

- `python_queue` - SQLite-backed local queue (no external deps; the default)
- `rabbitmq` - RabbitMQ (legacy, to be removed in the next major; needs the
  `naas-abi-core[rabbitmq]` extra and the `legacy` compose profile)

**Triple Store:**

- `fs` - Filesystem-based (local dev, no server required)
- `fuseki` - Apache Jena Fuseki (requires Docker container)
- `oxigraph` - Oxigraph (requires separate service)

**Vector Store:**

- `qdrant` - Qdrant vector DB (requires Docker container)
- `python` - In-memory (local dev, non-persistent)

**Key-Value Store:**

- `redis` - Redis (requires Docker container)
- `python` - In-memory dictionary (local dev, non-persistent)

## Code Style Guidelines

### Imports

- Prefer absolute imports from package roots (`naas_abi_core...`, `naas_abi...`).
- Group imports: standard library, third-party, local package.
- Keep imports explicit and remove unused ones.

### Formatting

- Use `ruff format` as canonical formatter.
- Preserve local style in touched files.
- Keep diffs clean (trailing commas in multiline blocks where appropriate).

### Typing

- Add type hints to new/changed public APIs.
- Prefer modern built-in generics (`list[str]`, `dict[str, Any]`).
- Keep port interfaces strongly typed; adapters must conform to port signatures.

### Naming

- Match naming conventions of the directory you modify.
- In `naas_abi_core`, many production files use `PascalCase.py`; keep that style in-place.
- Test functions use `test_...`; test classes use `Test...`.

### Error Handling

- Raise specific exceptions at domain/service boundaries.
- Catch exceptions at adapter or API boundaries for translation/fallback.
- Log actionable errors with repository logger utilities.
- Do not silently swallow exceptions.

### Testing Discipline

- Prefer TDD for new behaviors.
- Update colocated tests whenever behavior changes.
- Keep tests deterministic; isolate integration requirements explicitly.

## Agent Operating Rules

- Use `gh` CLI for PRs/issues/comments/checks/releases.
- Keep changes scoped; avoid broad refactors unless requested.
- Preserve existing architecture patterns over stylistic rewrites.
- If unsure, follow nearest module conventions.
- When a change introduces or updates an architecture-level decision (boundaries, ownership, cross-cutting configuration, major tradeoffs), add/update an ADR in `docs/adr/`.
- ADR files use `YYYYMMDD_topic.md` naming (e.g. `20260212_apache-jena-fuseki-default-triplestore.md`) and must include at least: Status, Date, Context, Decision, Consequences.

## Quick Cheat Sheet

```bash
# Setup (first time)
uv sync --all-extras
uv pip install greenlet
cd libs/naas-abi/naas_abi/apps/nexus/apps/web && pnpm install && cd ../../../../..

# Development
make deps           # Install/sync dependencies
make check          # Lint + type check
make fmt            # Format code
make test           # Run tests
uv build            # Build packages

# Stack management (Docker, on NATS)
abi stack start     # Start all services
abi stack status    # Check health
abi stack logs      # View logs
abi stack stop      # Stop services
abi stack start --legacy   # Legacy: + Dagster, RabbitMQ bus, engine without NATS

# Dev runtime (no Docker, needs nats-server on PATH)
uv run abi dev up -d   # oxigraph, nats, api, nexus-web
abi dev status         # Services and ports
abi dev down           # Stop them
abi dev up -d --without-nats   # Legacy: in-process engine, no broker

# Docker services
docker compose up -d postgres fuseki nats       # Infrastructure
docker compose --profile legacy up -d dagster   # Legacy containers
docker compose ps                               # Check status
docker compose logs -f <service>                # View logs
```

## Critical Adapter Implementation Rule

When creating or modifying secondary adapters, **ALL abstract methods from the port interface MUST be implemented**. Python will refuse to instantiate the class otherwise. For features not supported by an adapter, implement the method to raise `NotImplementedError` with a descriptive message.

## Hosted development environment instructions

The Cloud VM has no Docker, so use the **no-Docker `abi dev` runtime** (backed by `config.yaml`: Oxigraph/SQLite/filesystem adapters, on NATS). `abi stack start` and `config.local.yaml` require Docker (Postgres/Fuseki/Qdrant/Redis/MinIO/NATS) and will not work here. The update script installs deps (`uv sync --all-extras` + `pnpm install` for the web app) and Ollama if missing; it does **not** pull the ~2 GB models on every boot. Do not re-run those to "start" anything. `abi dev up` also needs **`nats-server` 2.14+ on `PATH`**: check with `nats-server --version`, and if it is missing install a release binary (https://github.com/nats-io/nats-server/releases) into `~/.local/bin`.

Default is **local-first Ollama** (`qwen-2.5-3b` chat + `nomic-embed-text` embeddings). Before first chat: `ollama serve` (if not already running) and `make ollama-models`.

Run all four services with `uv run abi dev up -d`, then `abi dev status` / `abi dev ports` / `abi dev logs <service> -f` (services: `oxigraph`, `nats`, `api`, `nexus-web`; Dagster is legacy and only starts with `--without-nats`). Stop them with `abi dev down`. Standard lint/test/build commands are documented above (`make check`, `make test`, targeted `uv run pytest ...`).

Non-obvious gotchas discovered during setup:

- **`.env` is required and gitignored.** It is auto-created on first `abi dev up`, seeding the admin login, `ABI_API_KEY` and the NATS secrets (`NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD`, `NATS_JWT_SECRET`). The engine renders `config.yaml` through Jinja and **hard-fails non-interactively (no TTY) on missing `{{ secret.X }}` in active (non-comment) YAML**. Full-line YAML comments are left unrendered, so commented-out modules can keep example `{{ secret.X }}` placeholders. Deploy placeholders are in `.env.example` (`NAAS_API_KEY`, `ABI_API_KEY`, `NEXUS_API_URL`): copy those if missing. The root config also names `OPENAI_API_KEY`, `OPENROUTER_API_KEY` and `GITHUB_ACCESS_TOKEN` in active YAML, so set them (a placeholder lets the API boot) through environment secrets or `.env`.
- **NATS ports are offset too.** `abi dev up` starts its own `nats-server` on an offset client port and hands the api its URL through `.abi/dev/dev.overlay.yaml`; the `127.0.0.1:4222` in `config.yaml` is the Docker stack's broker. `abi dev ports` lists the live ones; the broker's monitoring endpoint is the client port + 1000 (`/healthz`, `/connz`).
- **For capable cloud models:** set `global_config.ai_mode: "cloud"`, uncomment a cloud provider module in `config.yaml`, replace `SECRET_REF` with a real Jinja secret, and add its key via environment secrets or `.env`.
- **First API boot is slow (~2-3 min):** the worker loads every module/ontology and runs Nexus SQLite migrations before serving. Watch `abi dev logs api`; it is ready when `/docs` returns 200 (`GET http://localhost:<api-port>/docs`).
- **Ports are offset per worktree** (see `abi dev ports`), so they are not the config defaults. `abi dev` injects `OXIGRAPH_URL` into each service; the `config.yaml` default `:7878` is not the live port. To run a test that builds its own engine against the live triple store, pass `OXIGRAPH_URL=http://127.0.0.1:<oxigraph-port>`.
- **Login:** `admin@example.com` with the password generated into `.env` as `NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD` (printed by `abi dev up`). There is no default password. Web UI is the `nexus-web` port.
