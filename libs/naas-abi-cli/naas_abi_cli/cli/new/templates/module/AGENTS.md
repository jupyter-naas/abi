# {{module_name_pascal}} Module — AGENTS.md

> Canonical guidance for coding agents working inside this module. Keep this file up to date as the module evolves.

## What this module is

`{{module_name_snake}}` is an ABI module scaffolded with `abi new module`. It subclasses `BaseModule` from `naas_abi_core.module.Module` and registers itself in the engine's module registry when enabled in `config.yaml`.

A module is the **unit of composition** in ABI: it bundles agents, integrations, workflows, pipelines, orchestrations, and ontologies behind a single declared surface (dependencies + configuration).

## Layout

```
{{module_name_snake}}/
├── AGENTS.md          # this file
├── __init__.py        # ABIModule(BaseModule) — dependencies + Configuration + hooks
├── agents/            # IntentAgent / Agent definitions (see naas-abi-core/services/agent)
├── integrations/      # typed wrappers over third-party APIs
├── workflows/         # multi-step automations
├── pipelines/         # data pipelines
├── orchestrations/    # scheduler / orchestrator definitions
└── ontologies/        # RDF/OWL/TTL schemas this module reasons over
```

Empty sub-folders are fine — only fill the ones you need.

## The `ABIModule` (`__init__.py`)

```python
class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",   # or another LLM provider
        ],
        services=[
            # Secret,
            # TripleStoreService,
            # ObjectStorageService,
            # VectorStoreService,
            # BusService,
            # KeyValueService,
        ],
    )

    class Configuration(ModuleConfiguration):
        # typed config fields go here, e.g.
        # github_access_token: str
        # datastore_path: str = "{{module_name_snake}}"
        pass

    def on_load(self):                # constructor-like; no service access yet
        super().on_load()

    def on_initialized(self):         # services + other modules are ready
        super().on_initialized()

    def api(self, app: FastAPI) -> None:   # optional FastAPI hook
        pass
```

Lifecycle order:

1. `on_load()` — called as each module is being discovered. **Do not** access other modules or services here.
2. `on_initialized()` — called after every module has loaded. Safe to access `self.engine.services.<name>` and other modules.
3. `api(app)` — called when the framework wires the FastAPI app. Mount routes / wire `app.state` here.

## Configuration

Enable this module in `config.yaml` at the project root:

```yaml
modules:
  - module: {{module_name_snake}}
    enabled: true
    config:
      # values matching Configuration(ModuleConfiguration) fields
```

Secrets are resolved through the `secret` service — reference them as `{% raw %}{{ secret.MY_KEY }}{% endraw %}` in the config and back them in `.env` (or another secret adapter).

## Conventions

- File naming: `PascalCase.py` for production code (`{{module_name_pascal}}Agent.py`, `{{module_name_pascal}}Integration.py`), `<Name>_test.py` for tests.
- Agent constants exposed by every `<Name>Agent.py`:
  - `NAME`, `SLUG`, `TYPE`, `DESCRIPTION`, `AVATAR_URL`, `MODEL`, `SYSTEM_PROMPT`, `INTENTS`, plus a `create_agent(shared_state=None, configuration=None) -> IntentAgent` factory.
- Integration files (`<Name>Integration.py`) hold the **typed API wrapper** — no LLM calls there; that goes in the agent.
- Workflows / pipelines / orchestrations are individually testable units — add a `<Name>_test.py` next to each.

## Adding things to this module

```bash
# From the project root:
abi new agent <name>          ./<this-module-path>/agents
abi new integration <name>    ./<this-module-path>/integrations
abi new workflow <name>       ./<this-module-path>/workflows
abi new pipeline <name>       ./<this-module-path>/pipelines
abi new orchestration <name>  ./<this-module-path>/orchestrations
```

Each command scaffolds a `PascalCase.py` file from the CLI's templates. After scaffolding, wire the new component into the module:

- New **agent**: import in `agents/__init__.py` if you re-export it; register in `INTENTS` if it's discoverable by a coordinator.
- New **integration**: typically used by an agent's tools — bind it as a tool inside the agent.
- New **workflow / pipeline / orchestration**: expose a `run(...)` (or equivalent) entry point and add it to the relevant agent's toolset, schedule, or API route.

## Using core services

Declare the service in `dependencies.services`:

```python
dependencies = ModuleDependencies(
    modules=[...],
    services=[ObjectStorageService, TripleStoreService],
)
```

Then access them in `on_initialized()` or downstream code via `self.engine.services.<name>`. Service docs live in the upstream submodule at [`../../.abi/libs/naas-abi-core/naas_abi_core/services/`](../../.abi/libs/naas-abi-core/naas_abi_core/services/):

- Caching, KV, secrets → [`cache`](../../.abi/libs/naas-abi-core/naas_abi_core/services/cache/AGENTS.md), [`keyvalue`](../../.abi/libs/naas-abi-core/naas_abi_core/services/keyvalue/AGENTS.md), [`secret`](../../.abi/libs/naas-abi-core/naas_abi_core/services/secret/AGENTS.md)
- Persistence → [`object_storage`](../../.abi/libs/naas-abi-core/naas_abi_core/services/object_storage/AGENTS.md), [`triple_store`](../../.abi/libs/naas-abi-core/naas_abi_core/services/triple_store/AGENTS.md), [`vector_store`](../../.abi/libs/naas-abi-core/naas_abi_core/services/vector_store/AGENTS.md)
- Messaging → [`bus`](../../.abi/libs/naas-abi-core/naas_abi_core/services/bus/AGENTS.md), [`event`](../../.abi/libs/naas-abi-core/naas_abi_core/services/event/AGENTS.md)
- LLM + agents → [`model_registry`](../../.abi/libs/naas-abi-core/naas_abi_core/services/model_registry/AGENTS.md), [`agent`](../../.abi/libs/naas-abi-core/naas_abi_core/services/agent/AGENTS.md)
- Email, ontology NER, activity log → [`email`](../../.abi/libs/naas-abi-core/naas_abi_core/services/email/AGENTS.md), [`ontology`](../../.abi/libs/naas-abi-core/naas_abi_core/services/ontology/AGENTS.md), [`activity_log`](../../.abi/libs/naas-abi-core/naas_abi_core/services/activity_log/AGENTS.md)

## Tests

```bash
# Whole module
uv run pytest <path-to-this-module>

# Single file
uv run pytest <path-to-this-module>/agents/{{module_name_pascal}}Agent_test.py -v
```

Always test:

- Each agent's `create_agent().invoke(...)` over realistic prompts.
- Each integration's wrapper methods with the HTTP layer mocked.
- Module-level `on_load()` smoke test (`on_load_test.py`) — confirms the module loads with a minimal config.

## Architecture rules (non-negotiable)

1. **Hexagonal.** No direct infrastructure calls from agent / workflow code — go through a port.
2. **All abstract port methods MUST be implemented** in every secondary adapter (raise `NotImplementedError` for unsupported operations).
3. **Self-contained.** Don't reach into another module's internals — depend on it via `ModuleDependencies.modules` and use its public surface.
4. **Typed configuration.** Add fields to `Configuration(ModuleConfiguration)`; don't read `os.environ` directly.
5. **Tests colocated** as `<Name>_test.py` next to the file under test.
