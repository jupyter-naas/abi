# {{project_name}} — AGENTS.md

> Canonical guidance for coding agents working in this project. Read this first; then read the nearest `AGENTS.md` in any subdirectory you open.

## What this project is

`{{project_name}}` is an ABI project scaffolded with `abi new project`. It runs on top of the **ABI framework** (`naas-abi-core`, `naas-abi`, `naas-abi-cli`, `naas-abi-marketplace`) and packages your own logic as one or more **modules** under `src/{{project_name_snake}}/`.

The framework provides ports-and-adapters services (cache, bus, event, triple_store, vector_store, object_storage, secret, model_registry, agent, …). Your project consumes them through the standard service surface — never with direct infrastructure calls.

## Where the framework lives (read this!)

The upstream **ABI framework** is checked out at [`.abi/`](.abi) as a git submodule. Every framework AGENTS.md, service port, adapter, and reference scaffold is readable locally without leaving the project.

When you need framework context:

- **Per-service docs**: [`.abi/libs/naas-abi-core/naas_abi_core/services/<name>/AGENTS.md`](.abi/libs/naas-abi-core/naas_abi_core/services/) — port, adapters, factory, tests, "how to add an adapter".
- **Marketplace map**: [`.abi/libs/naas-abi-marketplace/AGENTS.md`](.abi/libs/naas-abi-marketplace/AGENTS.md) — LLM providers, app integrations, domain experts, module conventions.
- **Root agent guide**: [`.abi/AGENTS.md`](.abi/AGENTS.md) — service map and architecture rules.

The submodule is pinned to a specific commit. To pull upstream updates:

```bash
git submodule update --remote .abi
git add .abi && git commit -m "Bump .abi to latest"
```

If you cloned this project without `--recurse-submodules`, run:

```bash
git submodule update --init --recursive
```

## Layout

```
{{project_name}}/
├── AGENTS.md              # this file
├── README.md
├── pyproject.toml         # uv-managed dependencies
├── Dockerfile
├── config.yaml            # base config (modules + services)
├── config.local.yaml      # local-dev overrides (localhost hosts)
├── config.remote.yaml     # remote / production overrides
├── .env                   # secrets + env vars
├── .abi/                  # ← upstream ABI framework (git submodule, read-only reference)
└── src/
    └── {{project_name_snake}}/      # your default module — see its AGENTS.md
        ├── __init__.py              # ABIModule(BaseModule) — deps + Configuration
        ├── agents/
        ├── integrations/
        ├── workflows/
        ├── pipelines/
        ├── orchestrations/
        └── ontologies/
```

Every module under `src/` should have its own `AGENTS.md`. The default module already ships with one — keep it up to date when you add agents/workflows/integrations.

**Do not edit files under `.abi/`** — it's a submodule. Treat it as read-only documentation and reference source.

## How modules work (quick recap)

A module is a class that subclasses `BaseModule` and declares:

- `dependencies: ModuleDependencies` — other modules + core services it needs (e.g. `ObjectStorageService`, `TripleStoreService`, an LLM provider module from the marketplace).
- `Configuration(ModuleConfiguration)` — typed config fields validated at load time.
- Lifecycle hooks: `on_load()` (constructor-like, no service access yet), `on_initialized()` (post-load, services are ready), `api(app)` (FastAPI integration).

Modules are enabled in `config.yaml`:

```yaml
modules:
  - module: {{project_name_snake}}
    enabled: true
    config:
      # fields declared in Configuration
```

The `{% raw %}{{ secret.X }}{% endraw %}` syntax in config files is resolved by the `secret` service against `.env` / Naas / dotenv adapters.

## Commands

```bash
# Install deps
uv sync --all-extras

# Lint + type check
uvx ruff check src
uvx ruff format src

# Run tests
uv run pytest

# Single test
uv run pytest src/{{project_name_snake}}/agents/{{project_name_pascal}}Agent_test.py -v

# Start the local stack (Postgres, Fuseki, Qdrant, MinIO, RabbitMQ as needed)
abi stack start
abi stack status
abi stack logs
abi stack stop

# Start only the infrastructure your modules need
docker compose up -d postgres fuseki

# Add a new agent / integration / workflow / pipeline / orchestration to a module
abi new agent <name> src/{{project_name_snake}}/agents
abi new integration <name> src/{{project_name_snake}}/integrations
abi new workflow <name> src/{{project_name_snake}}/workflows
abi new pipeline <name> src/{{project_name_snake}}/pipelines
abi new orchestration <name> src/{{project_name_snake}}/orchestrations

# Scaffold an additional module alongside the default
abi new module <name> src
```

## Architecture rules (non-negotiable)

1. **Hexagonal architecture.** Domain logic in services / agents must never depend on concrete infrastructure. Add a port + adapter instead.
2. **Self-contained modules.** Every module owns its agents, integrations, workflows, pipelines, and ontologies under one directory. Cross-module reach goes through declared `dependencies`.
3. **All abstract port methods MUST be implemented** in every secondary adapter. Raise `NotImplementedError("...")` with a clear message for unsupported operations — Python will refuse to instantiate the class otherwise.
4. **Tests live next to the code** as `<Name>_test.py`. Run them with `uv run pytest`.
5. **Configuration is typed.** Add fields to `Configuration(ModuleConfiguration)` rather than reading `os.environ` directly inside modules.

## Naming conventions

- Module directories: `snake_case` (Python package).
- Agent / integration / workflow / pipeline files: `PascalCase.py` (e.g. `MyAgent.py`, `GitHubIntegration.py`).
- Tests: `<Name>_test.py` next to the file under test.
- Agent constants: `NAME`, `SLUG`, `DESCRIPTION`, `AVATAR_URL`, `MODEL`, `SYSTEM_PROMPT`, plus a `create_agent(...)` factory.

## Adding to the project

| I want to … | How |
|---|---|
| Add a new module | `abi new module <kebab-name> src` |
| Add an agent | `abi new agent <name> src/{{project_name_snake}}/agents` |
| Add a third-party integration | `abi new integration <name> src/{{project_name_snake}}/integrations` |
| Add a workflow | `abi new workflow <name> src/{{project_name_snake}}/workflows` |
| Add a data pipeline | `abi new pipeline <name> src/{{project_name_snake}}/pipelines` |
| Add an orchestration | `abi new orchestration <name> src/{{project_name_snake}}/orchestrations` |
| Use a marketplace module (e.g. GitHub, Claude) | Add it to `config.yaml` under `modules:` |
| Use a core service | Declare it in your module's `dependencies.services`, then access via `self.engine.services.<name>` |

## Configuration files

| File | Purpose |
|---|---|
| `config.yaml` | Base config — modules and service adapters |
| `config.local.yaml` | Local overrides (Docker hosts → `localhost`) |
| `config.remote.yaml` | Production overrides |
| `.env` | Secrets and environment variables resolved by the `secret` service |

The `secret` resolver merges multiple adapters in order — `.env` typically wins for local development, with Naas / vault adapters as fallback in production.

## See also

- Default module guide: [`src/{{project_name_snake}}/AGENTS.md`](src/{{project_name_snake}}/AGENTS.md)
- Framework reference (read-only): [`.abi/AGENTS.md`](.abi/AGENTS.md)
- Service catalog: [`.abi/libs/naas-abi-core/naas_abi_core/services/`](.abi/libs/naas-abi-core/naas_abi_core/services/) — each subdirectory has its own AGENTS.md.
- Marketplace catalog: [`.abi/libs/naas-abi-marketplace/AGENTS.md`](.abi/libs/naas-abi-marketplace/AGENTS.md) — pluggable LLMs, app integrations, domain experts.
