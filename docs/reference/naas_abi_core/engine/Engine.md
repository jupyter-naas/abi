# Engine

## What it is
- `Engine` is the runtime orchestrator for `naas_abi_core`.
- Responsibilities:
  - Load engine configuration.
  - Resolve module dependencies and load services/modules.
  - Optionally load ontologies into a triple store.
  - Publish process-wide defaults for the event service, model registry, and agent checkpointer.
  - In NATS mode: claim ownership/lease, expose services over NATS, host jobs, and support graceful shutdown/drain.

## Public API

### Class: `Engine(IEngine)`
#### Constructor
- `Engine(configuration: str | None = None)`
  - Loads `EngineConfiguration` (optionally from a provided configuration identifier/path).
  - Prepares module/service loaders.
  - Initializes NATS-related state so `shutdown()` is safe even if `load()` was never called.

#### Properties
- `configuration -> EngineConfiguration`
  - Loaded engine configuration.

- `modules -> dict[str, BaseModule]`
  - Loaded modules keyed by module name.
  - Raises `RuntimeError` if accessed before modules are loaded (i.e., before `load()` completes).

- `services -> IEngine.Services`
  - Loaded services.
  - In NATS mode may return service facades from `EngineNATSDependencies` rather than locally loaded services.

- `instance_id -> str`
  - Unique id for this engine instance; used as lease-holder id / owner id in NATS session subjects.

- `hosts_jobs -> bool`
  - Whether this engine hosts jobs (NATS mode with `nats.jobs.enabled`).

#### Methods
- `load(module_names: list[str] | None = None) -> None`
  - Loads telemetry, resolves module dependencies, claims ownership in NATS mode, loads services, binds agent memory, optionally exposes services over NATS, loads modules, validates model registry defaults, optionally loads ontologies, publishes default services to process context, initializes modules, and starts jobs (depending on NATS ownership/role).
  - On failure: attempts `shutdown()` before re-raising.

- `job_owners() -> dict[str, object]`
  - Returns job owners keyed by owner id.
  - Includes:
    - Loaded modules
    - Kernel/service job owners when applicable (e.g., dataset maintenance, agent memory jobs, and service adapter-provided job owners).

- `on_initialized() -> None`
  - Calls `on_initialized()` on every loaded module.

- `shutdown() -> None`
  - Gracefully stops jobs and NATS-exposed services (if started), releases ownership lease, clears process-wide defaults, closes NATS dependencies/runtime.
  - Safe to call multiple times, including before `load()`.

## Configuration/Dependencies
- Configuration:
  - `EngineConfiguration.load_configuration(...)`
  - Telemetry: `EngineTelemetryLoader.configure(configuration.telemetry)`
  - Ontology loading:
    - Requires `services.triple_store_available()`
    - Skipped when `configuration.global_config.skip_ontology_loading` is `True`

- Loaders/Dependencies:
  - `EngineModuleLoader` (dependency resolution, module ordering, module loading, model-provider discovery)
  - `EngineServiceLoader` (service loading, backend locality discovery)
  - `EngineOntologyLoader.load_ontologies(triple_store, ordered_modules)`
  - NATS mode (only when `configuration.nats` is set):
    - `EngineOwnershipLoader` (lease/ownership claim, keep/takeover, release/close)
    - `EngineNATSDependencies` (build service exposure dependencies or client facades)
    - `EngineNATSLoader` (expose services/overflow over NATS)
    - `EngineJobLoader` (host module/kernel jobs)

- Process-wide context publication (from `naas_abi_core.engine.context`):
  - `set_default_event_service(...)`
  - `set_default_model_registry(...)`
  - `set_default_agent_checkpointer(...)`

## Usage
```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()  # or Engine(configuration="path-or-id")
engine.load(module_names=["chatgpt"])

print("Instance:", engine.instance_id)
print("Modules:", list(engine.modules.keys()))
print("Has jobs hosting enabled:", engine.hosts_jobs)

# When done (especially in NATS mode):
engine.shutdown()
```

## Caveats
- Do not access `engine.modules` before `load()` completes.
  - Accessing too early raises `RuntimeError` (common mistake: using `self.engine.modules` in module constructors or `on_load`).

- In NATS mode, engine role affects behavior:
  - A **client** engine uses NATS client facades and does not load ontologies or host jobs.
  - A **serving** engine may expose services over NATS and host jobs; shutdown attempts to drain/stop primary adapters.
