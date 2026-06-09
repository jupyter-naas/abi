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
| `bus` | Pub/sub + durable work-queue message broker | [services/bus/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/bus/AGENTS.md) |
| `cache` | Multi-tier (hot/cold) cache with decorator API | [services/cache/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/cache/AGENTS.md) |
| `email` | Transactional email sending (SMTP / SES / FS) | [services/email/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/email/AGENTS.md) |
| `event` | Durable typed event log + live pub/sub | [services/event/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/event/AGENTS.md) |
| `keyvalue` | Bytes-in/out KV store with TTL + atomic CAS/CAD | [services/keyvalue/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/keyvalue/AGENTS.md) |
| `model_registry` | Canonical-ID catalog of chat/embedding models | [services/model_registry/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/model_registry/AGENTS.md) |
| `object_storage` | S3-style blob storage (FS / S3 / Naas) | [services/object_storage/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/object_storage/AGENTS.md) |
| `ontology` | LLM-powered NER against an RDF/OWL ontology | [services/ontology/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/ontology/AGENTS.md) |
| `secret` | Layered secret store (dotenv / Naas / base64) | [services/secret/AGENTS.md](libs/naas-abi-core/naas_abi_core/services/secret/AGENTS.md) |
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

- Checked `.cursorrules`: not present.
- Checked `.cursor/rules/`: not present.
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
#   RABBITMQ_HOST=localhost (if using RabbitMQ)
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

Default admin credentials:

| Email | Password |
|---|---|
| `admin@example.com` | `Admin1234!` |

Password login is enabled via `auth_password_enabled: true` in `config.local.yaml`. Set it to `false` to switch back to magic link.

**How the password is set:** On first boot, the seeder looks for `NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD` in `.env`. If found, it uses that value. If missing, it generates a random password and writes it back to `.env`. The `.env` in this repo ships with `Admin1234!` pre-set, so all teammates get the same password as long as they don't delete that line.

If you see "Incorrect email or password":

**Option A (no data to keep):** Wipe and reseed.
```bash
docker volume rm abi_postgres_data
abi stack start
```

**Option B (keep existing data):** The user already exists with a mismatched hash. Add the missing key to `.env` then force-update the hash:
```bash
# 1. Add to .env if missing:
echo "NEXUS_USER_ADMIN_EXAMPLE_COM_EMAIL=admin@example.com" >> .env
echo "NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD=Admin1234!" >> .env

# 2. Reset the hash in Postgres directly:
HASH=$(docker exec abi-abi-1 python3 -c "import bcrypt; print(bcrypt.hashpw(b'Admin1234!', bcrypt.gensalt()).decode())")
docker exec abi-postgres-1 psql -U abi -d nexus -c "UPDATE users SET hashed_password='$HASH' WHERE email='admin@example.com';"
docker compose restart abi
```

## Stack Management

```bash
# Start full stack (requires RabbitMQ, Redis, Qdrant, MinIO)
abi stack start

# Start only infrastructure (Postgres + Fuseki)
docker compose up -d postgres fuseki

# Start with message bus
docker compose up -d postgres fuseki rabbitmq

# Check status
abi stack status

# View logs
abi stack logs          # All services
abi stack logs core     # Core API only
abi stack logs api      # Nexus API only
abi stack logs web      # Frontend only

# Stop services
abi stack stop
```

### Configuration Adapters

Services can be configured to use different adapters in `config.yaml`:

**Bus Service:**

- `rabbitmq` - Production message queue (requires Docker container)
- `python_queue` - Local in-memory queue (no external deps)

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

# Stack management
abi stack start     # Start all services
abi stack status    # Check health
abi stack logs      # View logs
abi stack stop      # Stop services

# Docker services
docker compose up -d postgres fuseki rabbitmq  # Infrastructure
docker compose ps                               # Check status
docker compose logs -f <service>                # View logs
```

## Critical Adapter Implementation Rule

When creating or modifying secondary adapters, **ALL abstract methods from the port interface MUST be implemented**. Python will refuse to instantiate the class otherwise. For features not supported by an adapter, implement the method to raise `NotImplementedError` with a descriptive message.
