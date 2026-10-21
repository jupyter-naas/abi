---
sidebar_position: 1
---

# Creating a Module

Modules are the primary extension unit of ABI. A module packages a set of related agents, integrations, pipelines, workflows, ontologies and apps into a self-contained unit that declares what it depends on.

Since 3.0 there are two kinds, and `abi new module` creates the remote one by default.

---

## Remote or in-engine?

| | Remote module (default) | In-engine module |
|---|---|---|
| Create it | `abi new module <name>` | `abi new module <name> --in-engine` |
| Runs | In its own process (`abi dev up`, a Compose service, any supervisor) | Inside the engine process |
| Registered by | Discovery, at run time: it is **not** listed under `modules:` | `modules:` in `config.yaml` |
| Imports | `naas_abi_sdk` only | `naas_abi_core` directly |
| Reaches services | Through NATS, async, only the services it declares | Through the engine (`self.engine.services.<name>`) |
| Offers | Agents, apps, jobs | Agents, workflows, pipelines, integrations, ontologies, apps, jobs |
| Needs the broker | Yes | Only in a NATS project; it also works with NATS off |

**Choose a remote module** when the module should have its own life:

- it has its own dependencies, which must not end up in the engine's environment;
- it should deploy, scale and restart on its own, and survive an engine restart (it renews its lease in discovery);
- a separate team ships it (`abi new module <name> --standalone` creates a repository of its own);
- what it needs is an agent, an app or scheduled work, through the SDK's facades of the kernel services.

**Choose an in-engine module** when it works on the engine's own objects and code:

- pipelines that write RDF to the triple store, workflows exposed as tools and REST endpoints, integrations, ontologies loaded into the knowledge graph;
- anything that imports `naas_abi_core`;
- a project that has no broker (NATS off), where a remote module would not run.

The scaffolds follow the kind: `abi new workflow`, `abi new pipeline` and `abi new integration` write `naas_abi_core` code, so they refuse to run inside a remote module (the error says what to do instead). A project can mix both kinds. This page covers the in-engine module. For the remote one, see [Build a Remote Module](/user-guide/build/sdk/build-a-remote-module).

:::note
In a project whose config has no `nats:` block, `abi new module <name>` creates an in-engine module and says so; `--remote` forces a remote one, which runs once the project is on NATS.
:::

---

## Where modules live

| Where | Path | Use for |
|---|---|---|
| Your project | `src/<name>/` (`abi new module <name> --in-engine`) | Your own modules |
| Marketplace | `naas_abi_marketplace.<ai\|applications\|domains>.<name>`, installed as a package extra | Ready-made providers, integrations and domain agents. See the [Marketplace](/user-guide/build/modules/marketplace/marketplace-overview) |
| Framework | `naas_abi` (Nexus and the core agents), `naas_abi_core.modules.*` | Shipped with ABI |

---

## Module structure

`abi new module <name> --in-engine` scaffolds:

```bash
src/my_module/
├── AGENTS.md               # guidance for coding agents working in the module
├── __init__.py             # ABIModule(BaseModule)
├── agents/                 # <Name>Agent.py
├── integrations/           # <Name>Integration.py: external API wrapper
├── pipelines/              # <Name>Pipeline.py: data into RDF
├── workflows/              # <Name>Workflow.py: business logic as tools and API
├── ontologies/             # modules/, processes/, queries/ (OWL/Turtle)
├── apps/                   # a Nexus app (manifest.json, index.html)
└── orchestrations/         # Dagster, legacy: only in a project without NATS
```

Only `__init__.py` is required; keep the folders you use. Each scaffold also holds a starter file (a sample agent, integration, pipeline, workflow and ontology). In a project without NATS the module gets an `orchestrations/` folder; in a NATS project it does not (see [module jobs](/user-guide/build/modules/module-jobs)).

---

## Module class

The scaffolded `__init__.py`:

```python
from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],                     # modules this one needs (loaded first)
        services=[TripleStoreService],  # services it uses
    )

    class Configuration(ModuleConfiguration):
        # Module-specific, typed config fields
        pass

    def on_load(self):
        # Called as the module is discovered. Do not touch services or other modules yet.
        super().on_load()

    def on_initialized(self):
        # Called after every module and service is loaded: safe to use them here.
        super().on_initialized()

    def api(self, app: FastAPI) -> None:
        # Optional: mount your own FastAPI routes.
        pass
```

Keep the `super().on_load()` and `super().on_initialized()` calls: the first discovers your agents, workflows, pipelines and ontologies, the second instantiates workflows, pipelines and tools.

The engine computes a load order from every module's `dependencies`. Circular dependencies fail fast.

---

## Enabling a module

Add it to `config.yaml`. In a project the module is a package under `src/`, so its name is the folder name:

```yaml
modules:
  - module: my_module
    enabled: true
    config:
      my_custom_field: "value"
```

`config:` is validated against your `Configuration` class: unknown keys are rejected. Secrets are written `{{ secret.MY_KEY }}` and resolved from the secret service (`.env` by default).

---

## Auto-discovery

When the engine loads your module, it discovers:

- **Ontologies**: every `*.ttl` file under `ontologies/` (recursively; a path containing `sandbox` is skipped). They are loaded into the triple store.
- **Agents**: every agent class (an `Agent` or `IntentAgent` subclass) defined in `agents/*.py`. The engine calls its `New()`, or the file's module-level `create_agent()` when it defines one.
- **Workflows, pipelines and tools**: classes under `workflows/`, `pipelines/` and `tools/` (recursively). The engine instantiates each with `New()` or with an empty `Configuration`; a class whose constructor needs arguments the engine cannot supply is skipped and logged.
- **Models**: `models/*.py`, registered in the model registry (provider modules).
- **Apps**: `apps/<name>/manifest.json`, listed in Nexus.
- **Orchestrations** (legacy): classes under `orchestrations/`, when `naas-abi-core[dagster]` is installed.

Every loaded agent gets REST endpoints, and workflows and pipelines with a typed `run(parameters)` get a `POST` route: see the [REST API](/user-guide/build/applications/api).

---

## Accessing services from within a module

Inside a module, `self.engine` is an `EngineProxy` that exposes only the services and modules you declared in `dependencies`:

```python
def on_initialized(self):
    super().on_initialized()
    triple_store = self.engine.services.triple_store
    triple_store.query("SELECT * WHERE { ?s ?p ?o } LIMIT 10")
```

Accessing an undeclared service raises a runtime error: this enforces explicit dependency contracts. (The model registry is the exception: every module can use it.) In NATS mode, the services you get are facades that call the kernel services over NATS, so the same code works if a service later runs in its own process.

Store files through the `object_storage` service rather than writing to the local disk; marketplace modules take a `datastore_path` setting for the prefix they use.

---

## Soft dependencies

Suffix a module name with `#soft` to declare an optional dependency:

```python
dependencies = ModuleDependencies(
    modules=["naas_abi_marketplace.ai.anthropic#soft"],
    services=[TripleStoreService],
)
```

The engine loads your module even if the soft dependency is absent.

---

## Scheduled work: module jobs

A module that must run something on a schedule, or when an event happens, declares a **job**. JetStream schedules it and delivers the trigger; there is no central scheduler. In NATS mode an in-engine module declares jobs the same way a remote module does, and the engine runs them; handlers may be synchronous (they run in a worker thread):

```python
from datetime import timedelta
from naas_abi_core.module.jobs import Cron, JobContext, job

class ABIModule(BaseModule):
    @job(triggers=(Cron("0 0 2 * * *", time_zone="UTC"),), timeout=timedelta(hours=1))
    def nightly_sync(self, ctx: JobContext) -> dict:
        ...
        return {"synced": 42}
```

`Cron` takes six fields, seconds first. Every declared job needs a handler. Runs, retries and logs show in the Nexus System app's **Jobs** tab. How jobs work, step by step: [Module jobs](/user-guide/build/modules/module-jobs); the full reference: [Remote Modules and Jobs](/developer-guide/architecture/remote-modules#module-jobs).

:::warning Legacy: Dagster orchestrations
Without NATS, jobs are only logged, not run. Dagster orchestrations (`abi new orchestration`, the `orchestrations/` folder) are the [legacy](/user-guide/build/applications/dagster) way to schedule work in a project without NATS. They need the `naas-abi-core[dagster]` extra and are removed in the next major.
:::

---

## Testing

Test the units of your module directly: a workflow's `run(...)`, a pipeline's graph, an integration with its HTTP layer mocked. They do not need an engine.

To check that the module loads, build an engine. In a NATS project `Engine()` connects to a broker, so either run one (`abi dev up`, or `abi stack start`) or point `ABI_CONFIG_OVERLAY` at a YAML file holding `nats: null`:

```python
# tests/test_my_module.py
from naas_abi_core.engine.Engine import Engine

def test_module_loads():
    engine = Engine()
    engine.load(module_names=["my_module"])
    assert "my_module" in engine.modules
```

Next steps: [Creating an Agent](/user-guide/build/agents/creating-an-agent), [Creating an Integration](/user-guide/build/agents/creating-an-integration), [Creating a Workflow](/user-guide/build/agents/creating-a-workflow), [Creating a Pipeline](/user-guide/build/knowledge-graph/creating-a-pipeline).
