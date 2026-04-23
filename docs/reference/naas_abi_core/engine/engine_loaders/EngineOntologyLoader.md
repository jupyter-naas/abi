# EngineOntologyLoader

## What it is
A small utility class that loads ontology schemas from a list of modules into a triple store.

## Public API
- `class EngineOntologyLoader`
  - `@classmethod load_ontologies(triple_store: TripleStoreService, modules: List[BaseModule]) -> None`
    - Iterates over each module’s `ontologies` and calls `triple_store.load_schema(ontology)` for each.
    - Emits a debug log message `"Loading ontologies"`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for debug logging.
  - `TripleStoreService` providing `load_schema(...)`.
  - `BaseModule` instances exposing an `ontologies` iterable.

## Usage
```python
from naas_abi_core.engine.engine_loaders.EngineOntologyLoader import EngineOntologyLoader

# triple_store: TripleStoreService
# modules: list[BaseModule] where each module has `.ontologies`
EngineOntologyLoader.load_ontologies(triple_store, modules)
```

## Caveats
- Assumes every module in `modules` has an `ontologies` attribute and the `triple_store` object implements `load_schema(ontology)`.
