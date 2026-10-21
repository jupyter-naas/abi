# BaseModule (Module.py)

## What it is
Core base classes for “ABI modules”. A module:
- Holds an `EngineProxy` and a validated Pydantic configuration.
- Discovers and loads ontologies (`*.ttl`), agents, orchestrations, workflows, pipelines, tools, and (optionally) models.
- Provides lifecycle hooks (`on_load`, `on_initialized`, `on_unloaded`) and an API extension point (`api`).

## Public API

### `class ModuleDependencies`
Container for declaring module dependencies.
- `ModuleDependencies(modules: list[str], services: list[type])`
- Properties:
  - `modules: list[str]` — dependent module identifiers.
  - `services: list[type]` — dependent service types.

### `class ModuleConfiguration(pydantic.BaseModel)`
Base configuration model for modules.
- Fields:
  - `global_config: GlobalConfig`
- Pydantic config:
  - `extra="forbid"` (unknown fields rejected)

### `class BaseModule(JobsMixin, Generic[TConfig])`
Base interface for ABI modules (also mixes in job declaration support via `JobsMixin`).
- Class attributes (metadata defaults):
  - `name`, `description`, `logo_url`, `slug`: `str`
  - `tags: list[str]`
  - `dependencies: ModuleDependencies` (defaults to empty)
- Constructor:
  - `BaseModule(engine: EngineProxy, configuration: TConfig)`
    - Asserts `configuration` is an instance of `ModuleConfiguration`.
    - Asserts the subclass defines `Configuration` and it is a subclass of `ModuleConfiguration`.
    - Stores a per-class singleton instance (retrievable via `get_instance()`).

#### Class methods
- `get_dependencies() -> list[str]`
  - Returns `cls.dependencies` if present, otherwise `[]` (note: may return a `ModuleDependencies` object at runtime).
- `get_instance() -> Self`
  - Returns the previously constructed instance for this module class.
  - Raises `ValueError` if the module class has not been instantiated.

#### Properties
- `engine -> EngineProxy`
- `configuration -> TConfig`
- `ontologies -> list[str]` — discovered `.ttl` ontology file paths.
- `agents -> list[type[Expose]]` — loaded agent classes.
- `integrations -> list[Integration]` — present but not populated in this file.
- `workflows -> list[Workflow]` — instantiated workflow objects (after `on_initialized()`).
- `pipelines -> list[Pipeline]` — instantiated pipeline objects (after `on_initialized()`).
- `tools -> list[object]` — instantiated tool objects (after `on_initialized()`).
- `orchestrations -> list[type[Orchestrations]]` — loaded orchestration classes.

#### Lifecycle / hooks
- `on_load() -> None`
  - Discovers ontologies under `<module_root>/ontologies/**/*.ttl` (skips any path containing `"sandbox"` case-insensitively).
  - Loads:
    - agents via `ModuleAgentLoader.load_agents(self.__class__)`
    - orchestrations via `ModuleOrchestrationLoader.load_orchestrations(self.__class__)`
    - workflow classes via `ModuleWorkflowLoader.load_workflows(self.__class__)`
    - pipeline classes via `ModulePipelineLoader.load_pipelines(self.__class__)`
    - tool classes via `ModuleToolLoader.load_tools(self.__class__)`
  - Optionally auto-loads models via `ModuleModelLoader.load_models(...)` if `engine.services.model_registry_available()` is true. Passes `configuration.include_models` if present.
- `on_initialized() -> None`
  - Calls `_ensure_processes_loaded()` to instantiate discovered workflows, pipelines, and tools.
- `_ensure_processes_loaded() -> None`
  - Instantiates discovered workflow/pipeline/tool classes using `naas_abi_core.utils.process_api.instantiate_all`.
  - Skips reloading once loaded; intended to be called from `on_initialized()`.
- `on_unloaded() -> None`
  - No-op by default.
- `api(app: fastapi.FastAPI) -> None`
  - Override to register FastAPI endpoints; no-op by default.

## Configuration/Dependencies
- Requires:
  - `EngineProxy`
  - A configuration instance that subclasses `ModuleConfiguration` and includes `global_config: GlobalConfig`.
- Subclass requirements:
  - Must define `Configuration` on the class, and it must subclass `ModuleConfiguration`.
- Optional:
  - Declare `dependencies = ModuleDependencies(modules=[...], services=[...])`.
- Uses loaders/utilities from `naas_abi_core.module.*` and `find_class_module_root_path()` to locate module root and discover assets.

## Usage

```python
from naas_abi_core.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies

class MyConfig(ModuleConfiguration):
    # Optional: include_models can be referenced by BaseModule.on_load if present
    include_models: list[str] | None = None

class MyModule(BaseModule[MyConfig]):
    Configuration = MyConfig
    dependencies = ModuleDependencies(modules=[], services=[])

    def on_initialized(self):
        super().on_initialized()
        # workflows/pipelines/tools are now instantiated (if discoverable)
        print(len(self.workflows), len(self.pipelines), len(self.tools))

# bootstrap (engine/global_config creation not shown)
# mod = MyModule(engine, MyConfig(global_config=global_cfg))
# mod.on_load()
# mod.on_initialized()
# same = MyModule.get_instance()
# print(same.ontologies)
```

## Caveats
- `get_instance()` raises `ValueError` until the module class has been instantiated.
- `get_dependencies()` is annotated as `list[str]` but returns `cls.dependencies` (a `ModuleDependencies` instance by default).
- Ontology discovery skips any `.ttl` file whose path contains `"sandbox"` (case-insensitive).
- Workflows/pipelines/tools are instantiated only after `on_initialized()` (via `_ensure_processes_loaded()`); `on_load()` only discovers their classes.
