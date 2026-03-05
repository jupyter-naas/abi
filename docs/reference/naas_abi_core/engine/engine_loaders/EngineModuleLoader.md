# EngineModuleLoader

## What it is
`EngineModuleLoader` discovers module dependencies, computes a deterministic load order, and imports/instantiates enabled ABI modules from an `EngineConfiguration`. Each loaded module is constructed with an `EngineProxy` and a validated Pydantic configuration.

## Public API
- **Class: `EngineModuleLoader`**
  - `__init__(configuration: EngineConfiguration)`
    - Stores engine configuration used to locate and configure modules.
  - `modules -> Dict[str, BaseModule]` (property)
    - Returns loaded module instances keyed by module name.
  - `module_load_order -> List[str]` (property)
    - Returns the computed module load order (topologically sorted).
  - `ordered_modules -> List[BaseModule]` (property)
    - Returns loaded module instances in `module_load_order`.
  - `get_module_dependencies(module_name: str, scanned_modules: List[str] = []) -> Dict[str, ModuleDependencies]`
    - Imports a configured module, calls `ABIModule.get_dependencies()`, and recursively resolves dependencies.
    - Supports “soft” dependencies via the `#soft` suffix (not required to be configured).
    - Detects circular dependency chains during dependency scanning.
  - `get_modules_dependencies(module_names: List[str] = []) -> Dict[str, ModuleDependencies]`
    - Resolves dependencies for all enabled modules in configuration, or only for the specified subset.
    - Persists results internally for later loading.
  - `load_modules(engine: IEngine, module_names: List[str] = []) -> Dict[str, BaseModule]`
    - Computes dependency load order and loads modules in that order.
    - For each enabled module:
      - Imports `module_config.module`
      - Validates `ABIModule.Configuration` (must be a subclass of `ModuleConfiguration`)
      - Instantiates `ABIModule(EngineProxy(...), cfg)`
      - Calls `module.on_load()`

## Configuration/Dependencies
- **Configuration source**
  - Uses `EngineConfiguration.modules` entries; each entry must have:
    - `module` (import path string)
    - `enabled` (bool)
    - `config` (dict passed into `ABIModule.Configuration(...)` along with `global_config`)
  - Uses `EngineConfiguration.global_config` when building each module configuration.

- **Module contract**
  - Importable module must expose:
    - `ABIModule` class
    - `ABIModule.get_dependencies() -> ModuleDependencies`
    - `ABIModule.Configuration` class (must be a subclass of `ModuleConfiguration`)
  - `ABIModule(...)` instance must be a `BaseModule` and must implement `on_load()`.

- **Runtime dependencies**
  - `importlib` for module importing
  - `pydantic_core` for configuration validation errors
  - `EngineProxy`, `IEngine`, `BaseModule`, `ModuleConfiguration`, `ModuleDependencies`

## Usage
```python
from naas_abi_core.engine.engine_loaders.EngineModuleLoader import EngineModuleLoader
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration

# engine: IEngine must be provided by your runtime.
# configuration: EngineConfiguration must contain module entries with module path, enabled flag, and config dict.

loader = EngineModuleLoader(configuration)
modules = loader.load_modules(engine)

# Access loaded modules
print(loader.module_load_order)
for m in loader.ordered_modules:
    print(type(m))
```

## Caveats
- **Dependency rules**
  - Non-soft dependencies (`"dep"`) must be present in the enabled dependency graph; otherwise loading aborts with `ValueError`.
  - Soft dependencies (`"dep#soft"`) may be absent from configuration; they are ignored if not configured.
- **Cycle handling**
  - Topological sort raises `ValueError` on circular dependencies.
  - `module_dependencies_recursive()` is explicitly not protected against cycles and should only be used after a successful topological sort.
- **Configuration validation**
  - Module configuration instantiation errors (Pydantic validation) are wrapped and raised as `ValueError`.
- **Special-case proxy unlock**
  - The `EngineProxy` is created with `unlocked=True` only when `module_name == "naas_abi"`.
