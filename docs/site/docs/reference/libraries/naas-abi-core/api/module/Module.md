# BaseModule

## What it is
A base class and supporting models for defining “modules” in `naas_abi_core`. A module:
- Is initialized with an `EngineProxy` and a validated `ModuleConfiguration`
- Can declare dependencies on other modules/services
- Can auto-discover ontology `.ttl` files from an `ontologies/` folder
- Can load agents and orchestrations via loader helpers
- Exposes lifecycle hooks (`on_load`, `on_initialized`, `on_unloaded`) and an optional FastAPI `api()` hook

## Public API

### `class ModuleDependencies`
Holds dependency declarations for a module.
- **Constructor**
  - `ModuleDependencies(modules: List[str], services: List[type])`
- **Properties**
  - `modules: List[str]` - module dependency names/identifiers
  - `services: List[type]` - service types required by the module

### `class ModuleConfiguration(pydantic.BaseModel)`
Base configuration model for modules.
- **Fields**
  - `global_config: GlobalConfig`
- **Pydantic behavior**
  - `extra="forbid"` (unknown fields rejected)

### `class BaseModule(Generic[TConfig])`
Base interface for modules (generic over a configuration type `TConfig` bound to `ModuleConfiguration`).

#### Class attributes
- `dependencies: ModuleDependencies` - default is `ModuleDependencies(modules=[], services=[])`
- `_instances: Dict[type, BaseModule]` - internal registry for `get_instance()`

#### Constructor
- `BaseModule(engine: EngineProxy, configuration: TConfig)`
  - Asserts `configuration` is a `ModuleConfiguration`
  - Asserts subclass defines `Configuration` class and that it is a subclass of `ModuleConfiguration`
  - Sets:
    - `module_path` (derived from `self.__module__`)
    - `module_root_path` (via `find_class_module_root_path()`)

#### Class methods
- `get_dependencies() -> List[str]`
  - Returns `getattr(cls, "dependencies", [])`.
  - Note: `dependencies` is a `ModuleDependencies` by default, despite the return type annotation.
- `get_instance() -> Self`
  - Returns the stored instance for the module class.
  - Raises `ValueError` if the class was not initialized.

#### Properties (read-only)
- `engine -> EngineProxy`
- `configuration -> TConfig`
- `ontologies -> List[str]` - populated by `on_load()` via filesystem scan
- `agents -> List[type[Agent]]` - set by `on_load()` via `ModuleAgentLoader`
- `integrations -> List[Integration]`
- `workflows -> List[Workflow]`
- `pipelines -> List[Pipeline]`
- `orchestrations -> List[type[Orchestrations]]` - set by `on_load()` via `ModuleOrchestrationLoader`

#### Lifecycle hooks
- `on_load()`
  - Loads ontologies from `<module_root_path>/ontologies/**/*.ttl`
  - Loads agents and orchestrations via loader helpers
- `on_initialized()`
  - Called after all modules are loaded and the engine is fully initialized (default: logs only)
- `on_unloaded()`
  - Default: no-op
- `api(app: fastapi.FastAPI) -> None`
  - Override to register FastAPI endpoints (default: no-op)

## Configuration/Dependencies
- **Configuration model**: subclasses must define an inner class attribute `Configuration` that subclasses `ModuleConfiguration`.
- **Dependencies declaration**: via the class attribute `dependencies` (a `ModuleDependencies` instance).
- **Filesystem**:
  - Ontologies are discovered only if an `ontologies/` directory exists under the module root path.
  - Only `*.ttl` files are collected recursively.

Key imports used:
- `fastapi.FastAPI`
- `pydantic.BaseModel`
- `naas_abi_core.engine.EngineProxy.EngineProxy`
- `naas_abi_core.engine.engine_configuration.EngineConfiguration.GlobalConfig`
- `ModuleAgentLoader`, `ModuleOrchestrationLoader`
- `find_class_module_root_path`

## Usage

```python
from naas_abi_core.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies

# EngineProxy is provided by naas_abi_core at runtime.
# Here it's typed as "object" just to keep the example minimal/runnable.
EngineProxy = object

class MyConfig(ModuleConfiguration):
    pass

class MyModule(BaseModule[MyConfig]):
    Configuration = MyConfig
    dependencies = ModuleDependencies(modules=["other_module"], services=[])

    def on_initialized(self):
        # Called after engine and all modules are initialized
        print("Module initialized")

engine = EngineProxy()
cfg = MyConfig(global_config=None)  # GlobalConfig instance is expected in real usage.
m = MyModule(engine=engine, configuration=cfg)
m.on_load()

# Access singleton-like instance (after initialization)
same = MyModule.get_instance()
```

## Caveats
- `BaseModule.__init__` enforces that subclasses define `Configuration` and that it subclasses `ModuleConfiguration`; otherwise it raises via `assert`.
- `get_instance()` only works after at least one instance of that module class has been constructed; otherwise it raises `ValueError`.
- `get_dependencies()` is annotated to return `List[str]`, but the default `dependencies` value is a `ModuleDependencies` instance; callers should not rely on the annotation alone.
