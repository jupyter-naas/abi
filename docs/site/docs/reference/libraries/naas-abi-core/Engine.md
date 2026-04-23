# Engine

The `Engine` is the runtime orchestrator for `naas-abi-core`.

## What it does

`Engine.load()` performs:

1. Module dependency resolution.
2. Service loading (only required services).
3. Module instantiation/loading.
4. Ontology loading into triple store.
5. Final `on_initialized()` lifecycle callback.

## Basic usage

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()
engine.load()

for name, module in engine.modules.items():
    print(name, module)
```turtle

Load a subset:

```python
engine = Engine()
engine.load(module_names=["my_module"])
```

## Access patterns

- `engine.configuration`: validated `EngineConfiguration`.
- `engine.services`: loaded runtime services (`triple_store`, `vector_store`, `secret`, etc.).
- `engine.modules`: loaded module instances keyed by module name.

## Safety behavior

- Accessing `engine.modules` before `load()` raises a runtime error.
- Missing required module dependencies fail fast.
- Circular module dependencies are rejected.

## Proxy behavior inside modules

Modules receive an `EngineProxy`, not the raw engine.

- `engine_proxy.modules`: only declared dependencies (unless unlocked).
- `engine_proxy.services`: only declared service dependencies.

This enforces dependency contracts at runtime and avoids accidental coupling.
