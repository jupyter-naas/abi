# Marketplace — AGENTS.md

> Scope: `libs/naas-abi-marketplace/`. Canonical reference for agents working anywhere in the marketplace. Read this **before** opening any subdirectory.

## What this package is

`naas-abi-marketplace` is a registry of **pluggable modules** that extend the core `naas-abi-core` framework with concrete LLMs, third-party integrations, and domain expertise. Every module is independently installable as an optional extra (e.g. `pip install naas-abi-marketplace[applications-github]`) and discovered at runtime by core's module loader.

A module is anything that subclasses `BaseModule` (from `naas_abi_core.module.Module`) and exposes:

- A `dependencies: ModuleDependencies` declaration (other modules + core services it needs).
- A `class Configuration(ModuleConfiguration)` with typed config fields (validated at load).
- An `on_load()` hook (or relies on `BaseModule.on_load()` auto-discovery).

If you're adding to the marketplace, you're almost always adding **one more module** under one of the four top-level categories below.

## Top-level layout

```
naas_abi_marketplace/
├── ai/                # AI provider modules (Claude, ChatGPT, Gemini, …)
├── applications/      # Third-party app integrations (GitHub, Postgres, LinkedIn, …)
├── domains/           # Domain expert agents (Software Engineer, Accountant, …)
├── __demo__/          # Reference implementations + sample apps
└── alpha/             # Experimental modules
```

Every category follows the **same module shape** — once you understand one, you understand them all.

## The Module Shape (canonical)

Every module under `ai/<name>/`, `applications/<name>/`, `domains/<name>/` looks roughly like:

```
<name>/
├── __init__.py        # ABIModule(BaseModule) — dependencies + Configuration
├── agents/            # <Name>Agent.py + <Name>Agent_test.py
├── models/            # (AI modules) one file per concrete LLM
├── integrations/      # (application modules) third-party API wrappers
├── workflows/         # multi-step automations
├── pipelines/         # (some domains) data pipelines
├── ontologies/        # RDF/OWL/TTL schemas the module reasons over
└── on_load_test.py    # optional smoke test for ABIModule.on_load()
```

Not every subdirectory is required — pick the ones that fit. **All files keep `PascalCase.py` naming for production code** and `*_test.py` for tests (run with `uv run pytest`).

## Categories

Each category has its own quick index — read these for a full per-module list:

- [`ai/AGENTS.md`](naas_abi_marketplace/ai/AGENTS.md) — LLM providers (11 modules, 42 models)
- [`applications/AGENTS.md`](naas_abi_marketplace/applications/AGENTS.md) — third-party integrations (47 modules)
- [`domains/AGENTS.md`](naas_abi_marketplace/domains/AGENTS.md) — domain expert agents (24 modules)

### `ai/` — LLM provider modules

11 providers: `bedrock`, `chatgpt`, `claude`, `deepseek`, `gemini`, `gemma`, `grok`, `llama`, `mistral`, `perplexity`, `qwen`. See [`ai/AGENTS.md`](naas_abi_marketplace/ai/AGENTS.md) for the per-provider table.

Each contains:

- `__init__.py` — `ABIModule` declaring `services=[ObjectStorageService, ModelRegistryService]` and a `Configuration` with the provider's API key.
- `models/<model_id>.py` — one file per concrete model that exposes `CANONICAL_ID`, `MODEL_ID`, `PROVIDER`, and a `model: ChatModel` instance. Auto-registered in the `ModelRegistryService` by `BaseModule.on_load()`.
- `agents/<Name>Agent.py` — top-level conversational agent bound to the provider's default model.
- `ontologies/` — provider/model RDF schemas.

**To add a new model**: drop a new file under `models/` exposing `CANONICAL_ID` + a `model` instance — no further wiring needed.

### `applications/` — third-party integrations

47 apps including: `airtable`, `aws`, `git`, `github`, `gmail`, `google_*`, `hubspot`, `linkedin`, `notion`, `postgres`, `salesforce`, `sendgrid`, `slack`, … Full grouped index in [`applications/AGENTS.md`](naas_abi_marketplace/applications/AGENTS.md).

Each contains:

- `__init__.py` — `ABIModule` listing required modules (usually an `ai/<provider>` for the agent's LLM) and config (API keys, tokens, datastore path).
- `integrations/<Name>Integration.py` — typed Python wrapper over the third-party API (REST / GraphQL / SDK).
- `agents/<Name>Agent.py` — an `IntentAgent` that exposes the integration's capabilities as tools.
- `ontologies/` — RDF representation of the third-party domain.

**To add a new application**: scaffold the directory with `__init__.py` + `integrations/` + `agents/`, model dependencies in `ModuleDependencies.modules`, declare config fields. Wire intents in the agent.

### `domains/` — domain expert agents

24 roles: `account-executive`, `accountant`, `business-development-representative`, `campaign-manager`, `community-manager`, `content-analyst`, `content-creator`, `content-strategist`, `customer-success-manager`, `data-engineer`, `devops-engineer`, `document`, `financial-controller`, `human-resources-manager`, `inside-sales representative`, `ontology_engineer`, `organizations`, `osint-researcher`, `private-investigator`, `project-manager`, `sales-development-representative`, `software-engineer`, `support`, `treasurer`. Grouped by category in [`domains/AGENTS.md`](naas_abi_marketplace/domains/AGENTS.md).

Each contains:

- `__init__.py` — `ABIModule` listing the LLM module it uses (usually `ai.chatgpt` or a specific provider).
- `agents/<RoleName>Agent.py` — an `IntentAgent` with role-specific `SYSTEM_PROMPT`, default `MODEL`, exposed `NAME` / `SLUG` / `DESCRIPTION` / `AVATAR_URL`.
- `workflows/` — role-specific automations (e.g. `CodeReviewWorkflow`, `ArchitectureDesignWorkflow`).
- `pipelines/` — (when present) reusable data pipelines.
- `ontologies/` — domain vocabulary (e.g. `ProgrammingLanguages.ttl`, `DesignPatterns.ttl`).
- `models/` — (when present) pinned model overrides for this domain.

**To add a new domain**: pick a role, create the dir with `__init__.py` declaring the LLM dependency, add the agent + workflows + ontology TTL. The role-naming convention is **kebab-case directory** (`software-engineer`), **PascalCase agent file** (`SoftwareEngineerAgent.py`), and `SLUG = "software-engineer"` inside the agent.

### `__demo__/` and `alpha/`

- `__demo__/` — reference implementations: `agents/MultiModelAgent.py`, `workflows/ExecutePythonCodeWorkflow.py`, `apps/` (Streamlit + dashboard / kanban / calendar / network visualization demos), `orchestration/` (Dagster definitions). Use these as the canonical "how it's done" examples when scaffolding.
- `alpha/` — experimental modules not yet promoted (`wsr`).

## Agent file conventions

Every `<Name>Agent.py` exposes a stable surface that downstream code (registries, UIs, the marketplace catalog) relies on:

```python
NAME         = "..."                              # human-readable
SLUG         = "..."                              # kebab-case routing id (domains)
TYPE         = "domain-expert" | "ai-provider" | "application"
DESCRIPTION  = "..."                              # one-line catalog blurb
AVATAR_URL   = "https://..."                      # public asset
MODEL        = "claude-sonnet-4.5" | ...          # canonical model id (resolved via ModelRegistryService)
SYSTEM_PROMPT = """..."""                         # role prompt
INTENTS      = [Intent(...), ...]                 # IntentAgent routing

def create_agent(
    shared_state: AgentSharedState | None = None,
    configuration: AgentConfiguration | None = None,
) -> IntentAgent:
    ...
```

Tests live next to the agent as `<Name>Agent_test.py` and exercise `create_agent().invoke(prompt)`.

## Module loading & configuration

Modules are enabled in `config.yaml` / `config.local.yaml` at the repo root:

```yaml
modules:
  - module: naas_abi_marketplace.ai.claude
    enabled: true
    config:
      anthropic_api_key: "{{ secret.ANTHROPIC_API_KEY }}"

  - module: naas_abi_marketplace.applications.github
    enabled: true
    config:
      github_access_token: "{{ secret.GITHUB_ACCESS_TOKEN }}"

  - module: naas_abi_marketplace.domains.software-engineer
    enabled: true
    config:
      datastore_path: "software-engineer"
```

The `{{ secret.X }}` syntax is resolved by the `secret` service (see [services/secret/AGENTS.md](../naas-abi-core/naas_abi_core/services/secret/AGENTS.md)). `dependencies.modules` are auto-loaded; you don't need to list a module's deps in `config.yaml`.

## Discovery cheat sheet

| I want to … | Look here |
|---|---|
| Find available LLMs / providers | `naas_abi_marketplace/ai/<provider>/models/` |
| See which third-party apps are wrapped | `naas_abi_marketplace/applications/` |
| Find a role-specific agent | `naas_abi_marketplace/domains/<role>/agents/` |
| Browse reusable workflows | `*/workflows/`, especially `__demo__/workflows/` and per-domain |
| Find a working scaffold to copy | `__demo__/agents/MultiModelAgent.py`, `__demo__/workflows/ExecutePythonCodeWorkflow.py` |
| Understand a module's config schema | Its `__init__.py` → `class Configuration` |
| Find a module's tests | `*_test.py` next to the file under test; `on_load_test.py` for module-load smoke tests |
| Install only what I need | `pip install naas-abi-marketplace[<group>-<name>]` — see `README.md` for extras list |

## Test commands

```bash
# Whole package
uv run pytest libs/naas-abi-marketplace

# One module
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/ai/claude
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/github
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/software-engineer

# A single agent test
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/github/agents/GitHubAgent_test.py -v
```

## Adding a new module (checklist)

1. Pick the category: `ai/`, `applications/`, or `domains/`.
2. Create `<name>/__init__.py` with an `ABIModule(BaseModule)`:
   - `dependencies` — list the modules and core services it needs.
   - `Configuration` — typed config fields; include a docstring config example for operators.
   - Override `on_load()` only if `BaseModule.on_load()` auto-discovery doesn't fit.
3. Add the appropriate sub-folders (`agents/`, `models/`, `integrations/`, `workflows/`, `ontologies/`) — only what you need.
4. Implement the agent with the conventional constants (`NAME`, `DESCRIPTION`, `SYSTEM_PROMPT`, `MODEL`, `create_agent`).
5. Write at least:
   - `<Name>Agent_test.py` — exercises `create_agent().invoke(...)`.
   - `on_load_test.py` — verifies `ABIModule().on_load()` works with a minimal config.
6. Register the module in `config.yaml` for stack-level enablement, and add a `pyproject.toml` optional-extra group if it pulls heavy dependencies.
7. Update `README.md` if the module is user-facing.

## See also

- Per-service docs (ports, adapters, factories): [`libs/naas-abi-core/naas_abi_core/services/*/AGENTS.md`](../naas-abi-core/naas_abi_core/services/)
- Root agent guidance: [`AGENTS.md`](../../AGENTS.md)
