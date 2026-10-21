# UpdateDataPropertyPipeline

## What it is
- A `Pipeline` that updates a single **data property** (literal value) for a given RDF subject/predicate in a triple store.
- It fetches the subject’s current graph, validates the predicate has exactly one existing value, removes the old triple, inserts the new literal, and returns the updated subject graph.
- Special case: when updating `rdfs:label`, it also inserts the same value as `skos:altLabel`.

## Public API
- `UpdateDataPropertyPipelineConfiguration(PipelineConfiguration)`
  - **Field**
    - `triple_store: ITripleStoreService` — service used to insert/remove triples.

- `UpdateDataPropertyPipelineParameters(PipelineParameters)`
  - **Fields**
    - `subject_uri: str` — subject URI (validated by `URI_REGEX`).
    - `predicate_uri: str` — predicate URI (must match `^http.+$`).
    - `object_new_value: str` — new literal value (see caveats about typing).
    - `language: Optional[str] = None` — optional language tag for string literals.

- `UpdateDataPropertyPipeline(Pipeline)`
  - `__init__(configuration: UpdateDataPropertyPipelineConfiguration)`
    - Initializes pipeline and SPARQL utilities (uses `ABIModule.get_instance().engine.services.triple_store` for SPARQL reads).
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Updates the property value in the configured triple store and returns the refreshed subject graph.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes a LangChain `StructuredTool` named `update_data_property` calling `run(...)`.
  - `as_api(...) -> None`
    - Stub; does not register any routes (returns `None`).

## Configuration/Dependencies
- Requires an implementation of `ITripleStoreService` with:
  - `insert(graph: rdflib.Graph)`
  - `remove(graph: rdflib.Graph)`
- Uses:
  - `rdflib` (`Graph`, `URIRef`, `Literal`, `RDFS`, `SKOS`, `XSD`)
  - `SPARQLUtils.get_subject_graph(subject_uri)` to read current triples for the subject.
- Logging via `naas_abi_core.logger`.

## Usage
```python
from rdflib import RDFS
from naas_abi_core.engine.Engine import Engine
from naas_abi.pipelines.UpdateDataPropertyPipeline import (
    UpdateDataPropertyPipeline,
    UpdateDataPropertyPipelineConfiguration,
    UpdateDataPropertyPipelineParameters,
)

engine = Engine()
engine.load(module_names=["naas_abi"])
triple_store = engine.services.triple_store

pipeline = UpdateDataPropertyPipeline(
    UpdateDataPropertyPipelineConfiguration(triple_store=triple_store)
)

graph = pipeline.run(
    UpdateDataPropertyPipelineParameters(
        subject_uri="http://ontology.naas.ai/abi/some-subject",
        predicate_uri=str(RDFS.label),
        object_new_value="Ford Motor Company",
        language="en",
    )
)

print(graph.serialize(format="turtle"))
```

## Caveats
- The pipeline expects `parameters` to be `UpdateDataPropertyPipelineParameters`; otherwise it raises `ValueError`.
- Update only succeeds when the subject has:
  - **exactly one** existing triple for `(subject, predicate, ?o)`.
  - If **zero** exist: returns an empty `Graph`.
  - If **multiple** exist: returns an empty `Graph`.
- `object_new_value` is declared as `str` in parameters, but `run()` contains branches for `float` and `int`; in typical Pydantic usage it may be coerced to `str`, so numeric-typed literals may not be produced as intended.
- SPARQL reads use the global engine’s triple store (`ABIModule.get_instance().engine.services.triple_store`), while writes use `configuration.triple_store`; these should refer to the same backend to avoid inconsistencies.
- When `predicate_uri` is `rdfs:label`, the pipeline also inserts `skos:altLabel` with the same literal.
