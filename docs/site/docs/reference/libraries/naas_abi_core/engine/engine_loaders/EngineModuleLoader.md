# EngineModuleLoader

## What it is
`EngineModuleLoader` discovers module dependencies, computes a safe load order, and imports/instantiates enabled ABI modules (implementations of `BaseModule`) using an `EngineProxy`.

## Public API
- `class EngineModuleLoader(configuration: EngineConfiguration)`
  - Loads and initializes configured modules for a given engine.

### Properties
- `modules -> Dict[str, BaseModule]`
  - Loaded module instances keyed by module name.
- `module_load_order -> List[str]`
  - Module names in computed load order (topological order).
- `ordered_modules -> List[BaseModule]`
  - Loaded module instances in load order.

### Methods
- `get_module_dependencies(module_name: str, scanned_modules: List[str] = []) -> Dict[str, ModuleDependencies]`
  - Imports a single module, calls `ABIModule.get_dependencies()`, and recursively resolves its module dependencies.
  - Detects circular dependencies during recursion using `scanned_modules`.
  - Supports *soft* dependencies by allowing `module_name` to end with `#soft` (missing soft modules return `{}`).

- `get_modules_dependencies(module_names: List[str] = []) -> Dict[str, ModuleDependencies]`
  - Builds the dependency map for all enabled modules in `EngineConfiguration.modules`.
  - If `module_names` is provided, only includes those modules; raises if a requested module is not enabled.

- `load_modules(engine: IEngine, module_names: List[str] = []) -> Dict[str, BaseModule]`
  - Resolves dependencies (if not already resolved), computes load order, imports modules, validates their configuration models, instantiates them, and calls `on_load()`.
  - Creates an `EngineProxy` per module; the proxy is created with `unlocked=True` only when `module_name == "naas_abi"`.

## Configuration/Dependencies
- Requires an `EngineConfiguration` containing:
  - `global_config` (passed into each module’s configuration model as `global_config=...`)
  - `modules`: list of module configs with at least:
    - `module` (import path string used by `importlib.import_module`)
    - `enabled` (bool)
    - `config` (dict passed to the module configuration model)

- Each importable module must expose:
  - `ABIModule` class
  - `ABIModule.get_dependencies() -> ModuleDependencies`
  - `ABIModule.Configuration` which must be a subclass of `ModuleConfiguration`
  - `ABIModule(...)` must produce an instance of `BaseModule` and support `on_load()`

- Uses:
  - `importlib` for dynamic imports
  - `pydantic_core` for catching configuration validation errors
  - `EngineProxy`, `IEngine`, `BaseModule`, `ModuleDependencies`, `ModuleConfiguration`

## Usage
```python
from naas_abi_core.engine.engine_loaders.EngineModuleLoader import EngineModuleLoader

# Provided by your application/runtime
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration
from naas_abi_core.engine.IEngine import IEngine

engine: IEngine = ...                     # your engine implementation
config: EngineConfiguration = ...          # populated EngineConfiguration

loader = EngineModuleLoader(config)

modules = loader.load_modules(engine)      # loads all enabled modules
print(loader.module_load_order)
print(list(modules.keys()))
```

To load a subset (must be enabled in configuration):
```python
modules = loader.load_modules(engine, module_names=["my_module_path"])
```

## Caveats
- Dependency load order is computed via topological sort; circular dependencies raise `ValueError`.
- Missing *required* dependencies (non-`#soft`) raise `ValueError` during sorting.
- `module_dependencies_recursive()` is explicitly **not** protected against circular dependencies and should only be used after a safe load order is established.
- `get_module_dependencies()` has a default argument `scanned_modules=[]` (mutable default); the method uses it read-only per call chain, but it is still a shared default object.
