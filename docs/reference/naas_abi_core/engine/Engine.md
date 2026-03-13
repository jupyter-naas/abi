# Engine

## What it is
- `Engine` is the main runtime orchestrator for **naas-abi-core**.
- It loads:
  - configuration (`EngineConfiguration`)
  - services (`EngineServiceLoader`)
  - modules (`EngineModuleLoader`)
  - ontologies (via `EngineOntologyLoader`, only if a triple store is available)
- It then initializes modules by calling `on_initialized()`.

## Public API

### Class: `Engine(IEngine)`
- **`Engine(configuration: str | None = None)`**
  - Creates an engine instance.
  - Loads configuration using `EngineConfiguration.load_configuration(configuration)`.
  - Prepares module and service loaders.

- **`load(module_names: List[str] = [])`**
  - Loads and initializes the engine.
  - Steps:
    - Resolve module dependencies for `module_names`.
    - Load engine services for those dependencies.
    - Load modules (passing the engine instance to the module loader).
    - If `services.triple_store_available()` is true, load ontologies into the triple store.
    - Call `on_initialized()`.

- **`on_initialized()`**
  - Calls `on_initialized()` on each loaded module.

#### Properties
- **`configuration -> EngineConfiguration`**
  - Returns the loaded engine configuration.

- **`modules -> Dict[str, BaseModule]`**
  - Returns loaded modules.
  - Raises `RuntimeError` if accessed before modules are loaded (e.g., during module construction or `on_load`).

- **`services -> IEngine.Services`**
  - Returns loaded engine services.

## Configuration/Dependencies
- **Configuration**
  - Loaded via `EngineConfiguration.load_configuration(configuration)`.
  - The `configuration` argument is passed through to that loader (string path or identifier, depending on implementation).

- **Loaders/Services**
  - `EngineModuleLoader`: resolves dependencies and loads modules.
  - `EngineServiceLoader`: loads engine services used by modules.
  - `EngineOntologyLoader`: loads ontologies when a triple store is available (`services.triple_store_available()`).

- **Logging**
  - Uses `naas_abi_core.logger` for debug/error output.

## Usage

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()  # or Engine(configuration="path/or/name")
engine.load(module_names=["chatgpt"])

# Access loaded components after load()
mods = engine.modules
svcs = engine.services
```

## Caveats
- Do **not** access `engine.modules` before `Engine.load()` completes.
  - Attempting to do so raises a `RuntimeError` and logs an error.
  - In particular: avoid accessing `self.engine.modules` from module constructors or `on_load`; modules are safe to access when `on_initialized` is called.
- Ontology loading is skipped when no triple store is available.
