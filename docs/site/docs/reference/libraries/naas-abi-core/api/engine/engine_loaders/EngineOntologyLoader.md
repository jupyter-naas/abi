# EngineOntologyLoader

## What it is
A small utility class that loads ontology schemas from a list of modules into a triple store.

## Public API
- `class EngineOntologyLoader`
  - `@classmethod load_ontologies(triple_store: TripleStoreService, modules: List[BaseModule]) -> None`
    - Iterates over `modules`, then over each module’s `ontologies`, and calls `triple_store.load_schema(ontology)` for each.
    - Emits a debug log: `"Loading ontologies"`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for debug logging.
  - `TripleStoreService` providing `load_schema(...)`.
  - `BaseModule` instances providing an `ontologies` iterable/attribute.

## Usage
```python
from naas_abi_core.engine.engine_loaders.EngineOntologyLoader import EngineOntologyLoader

# triple_store: TripleStoreService
# modules: list[BaseModule]
EngineOntologyLoader.load_ontologies(triple_store, modules)
```

## Caveats
- Expects each `module` to have an `ontologies` attribute; missing/invalid attributes will raise at runtime.
- The method does not handle exceptions from `triple_store.load_schema(...)`.
