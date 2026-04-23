# BaseModule (Module.py)

## What it is
Core base classes for “ABI modules”. A module:
- Holds an `EngineProxy` reference and validated configuration.
- Discovers module ontologies (`*.ttl`), agents, and orchestrations on load.
- Provides lifecycle hooks (`on_load`, `on_initialized`, `on_unloaded`) and an optional FastAPI extension point (`api`).

## Public API

### `class ModuleDependencies`
Container for declaring module dependencies.

- `ModuleDependencies(modules: List[str], services: List[type])`
- Properties:
  - `modules: List[str]` — dependent module names/identifiers.
  - `services: List[type]` — dependent service types.

### `class ModuleConfiguration(pydantic.BaseModel)`
Base configuration model for modules.

- Fields:
  - `global_config: GlobalConfig`
- Pydantic config:
  - `extra="forbid"` (unknown fields are rejected)

### `class BaseModule(Generic[TConfig])`
Base interface for ABI modules.

#### Constructor
- `BaseModule(engine: EngineProxy, configuration: TConfig)`
  - Requires `configuration` to be an instance of `ModuleConfiguration`.
  - Requires subclass to define a nested `Configuration` class that is a subclass of `ModuleConfiguration`.
  - Registers the created instance in a per-class singleton map.

#### Class attributes
- `dependencies: ModuleDependencies` — defaults to empty dependencies.

#### Class methods
- `get_dependencies() -> List[str]`
  - Returns `cls.dependencies` if present, otherwise `[]`.
  - Note: annotated as `List[str]`, but the default `dependencies` is a `ModuleDependencies` instance.
- `get_instance() -> Self`
  - Returns the previously constructed instance for this module class.
  - Raises `ValueError` if not initialized.

#### Properties
- `engine -> EngineProxy`
- `configuration -> TConfig`
- `ontologies -> List[str]` — paths to discovered `.ttl` files.
- `agents -> List[type[Expose]]` — loaded agent classes.
- `integrations -> List[Integration]` — list is defined but not populated in this file.
- `workflows -> List[Workflow]` — list is defined but not populated in this file.
- `pipelines -> List[Pipeline]` — list is defined but not populated in this file.
- `orchestrations -> List[type[Orchestrations]]` — loaded orchestration classes.

#### Lifecycle hooks
- `on_load()`
  - Loads ontologies from `<module_root>/ontologies/**/*.ttl` (skips files whose path contains `"sandbox"` case-insensitively).
  - Loads agents via `ModuleAgentLoader.load_agents(self.__class__)`.
  - Loads orchestrations via `ModuleOrchestrationLoader.load_orchestrations(self.__class__)`.
- `on_initialized()`
  - Intended for post-initialization work after all modules/services are available.
- `on_unloaded()`
  - No-op by default.
- `api(app: fastapi.FastAPI) -> None`
  - Override to register API endpoints; no-op by default.

## Configuration/Dependencies
- Requires:
  - `EngineProxy` for runtime engine access.
  - `ModuleConfiguration` (or subclass) with `global_config: GlobalConfig`.
- Subclass must define:
  - `class Configuration(ModuleConfiguration): ...`
- Optional dependency declaration:
  - `dependencies = ModuleDependencies(modules=[...], services=[...])`

## Usage

```python
from naas_abi_core.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies

# Minimal config subclass
class MyConfig(ModuleConfiguration):
    pass

class MyModule(BaseModule[MyConfig]):
    Configuration = MyConfig
    dependencies = ModuleDependencies(modules=[], services=[])

    def on_initialized(self):
        # post-init logic here
        ...

# Somewhere in your bootstrap code:
# engine = EngineProxy(...)
# cfg = MyConfig(global_config=...)
# mod = MyModule(engine, cfg)
# mod.on_load()
# mod.on_initialized()

# Later:
same_mod = MyModule.get_instance()
print(same_mod.ontologies)
```

## Caveats
- `get_instance()` only works after the module class has been instantiated at least once; otherwise it raises `ValueError`.
- `get_dependencies()` is typed as returning `List[str]`, but `dependencies` is a `ModuleDependencies` object by default; code consuming this should account for that.
- Ontology discovery skips any ontology file path containing `"sandbox"` (case-insensitive).
