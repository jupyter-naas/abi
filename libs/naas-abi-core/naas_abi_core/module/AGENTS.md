# Module loaders

> Scope: `libs/naas-abi-core/naas_abi_core/module/`. How a module discovers its components.

## Purpose

`BaseModule` is the unit of composition. `on_load` walks folders. `on_initialized` constructs what it can. The kernel API then calls `as_api` on the instances.

## Files

| File | Role |
|---|---|
| `Module.py` | `BaseModule` lists and lifecycle |
| `ModuleAgentLoader.py` | `agents/*.py` → `Expose` subclasses |
| `ModuleOrchestrationLoader.py` | `orchestrations/*.py` |
| `ModuleModelLoader.py` | `models/` → model registry |
| `ModuleComponentLoader.py` | Shared recursive folder walk |
| `ModuleWorkflowLoader.py` | `workflows/` → `Workflow` subclasses |
| `ModulePipelineLoader.py` | `pipelines/` → `Pipeline` subclasses |
| `ModuleToolLoader.py` | `tools/` → `Expose` and `BaseTool` subclasses |
| `../utils/process_api.py` | `instantiate_process`, default `run()` POST |

## Lifecycle

1. `on_load`: discover classes. Do not touch other modules or services.
2. `on_initialized`: `instantiate_all` on workflow, pipeline, and tool classes. Call `super().on_initialized()` if you override this hook.
3. Kernel `_load_runtime_routes`: agents via `New()` + `as_api`; processes via `mount_module_processes`.

A class that needs constructor config we cannot supply is skipped and logged. That is intentional. Do not invent a fake instance.

## Tools

`module.tools` is the walk #1195 needs (Nexus list and compose). HTTP is narrower: only an `Expose` with a live `as_api` (or a live `run()`) is mounted under `/tools`. A LangChain `BaseTool` is not given REST.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/module/ModuleComponentLoader_test.py -v
uv run pytest libs/naas-abi-core/naas_abi_core/module/ModuleModelLoader_test.py -v
```
