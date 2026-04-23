# Engine

## What it is
- `Engine` is the main runtime orchestrator for `naas_abi_core`.
- It loads configuration, resolves module dependencies, loads services and modules, optionally loads ontologies into a triple store, then notifies modules that initialization is complete.

## Public API

### Class: `Engine(IEngine)`
- **`Engine(configuration: str | None = None)`**
  - Loads an `EngineConfiguration` (optionally from a provided configuration path/identifier).
  - Prepares module and service loaders.

#### Properties
- **`configuration -> EngineConfiguration`**
  - Returns the loaded engine configuration.

- **`modules -> Dict[str, BaseModule]`**
  - Returns loaded modules keyed by name.
  - Raises `RuntimeError` if accessed before `load()` completes (e.g., inside module constructors or `on_load`).

- **`services -> IEngine.Services`**
  - Returns loaded services (as defined by `IEngine.Services`).

#### Methods
- **`load(module_names: List[str] = []) -> None`**
  - Resolves module dependencies.
  - Loads services required by the module set.
  - Loads modules.
  - If a triple store is available and ontology loading is not skipped, loads ontologies for ordered modules.
  - Calls `on_initialized()`.

- **`on_initialized() -> None`**
  - Calls `on_initialized()` on each loaded module.

## Configuration/Dependencies
- Depends on:
  - `EngineConfiguration.load_configuration(...)`
  - `EngineModuleLoader` (dependency resolution and module loading)
  - `EngineServiceLoader` (service loading)
  - `EngineOntologyLoader.load_ontologies(...)` (optional ontology loading)
  - `IEngine` and `BaseModule`
- Ontology loading behavior:
  - Runs only if `services.triple_store_available()` is true.
  - Skipped when `configuration.global_config.skip_ontology_loading` is true.

## Usage
```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()  # or Engine(configuration="path-or-id")
engine.load(module_names=["chatgpt"])

# After load() completes:
mods = engine.modules
svcs = engine.services
print("Loaded modules:", list(mods.keys()))
```

## Caveats
- Do not access `engine.modules` before `Engine.load()` finishes.
  - Accessing it too early raises `RuntimeError` and logs an error.
  - The error message indicates modules are accessible when `on_initialized` is called; avoid using `self.engine` in module constructors or `on_load`.
