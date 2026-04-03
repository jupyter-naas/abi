# UpdateDataPropertyPipeline

## What it is
- A pipeline that updates a single RDF *data property* (literal value) for a given subject and predicate in a triple store.
- It:
  - Loads the subject’s current graph from the triple store.
  - Validates that exactly one existing value exists for the predicate (otherwise fails).
  - Removes the old triple and inserts the new literal.
  - Special-cases `rdfs:label` by also inserting `skos:altLabel`.

## Public API

### Classes

- `UpdateDataPropertyPipelineConfiguration(PipelineConfiguration)`
  - **Purpose:** Holds dependencies for the pipeline.
  - **Fields:**
    - `triple_store: ITripleStoreService` - triple store service used to insert/remove triples.

- `UpdateDataPropertyPipelineParameters(PipelineParameters)`
  - **Purpose:** Input parameters for updating a property.
  - **Fields:**
    - `subject_uri: str` - subject URI (validated by `URI_REGEX`).
    - `predicate_uri: str` - predicate URI (must match `^http.+$`).
    - `object_new_value: str` - new literal value (annotated as `str`).
    - `language: Optional[str]` - optional language tag for the literal.

- `UpdateDataPropertyPipeline(Pipeline)`
  - **Purpose:** Executes the update and returns the updated subject graph.

### Methods

- `UpdateDataPropertyPipeline.run(parameters: PipelineParameters) -> rdflib.Graph`
  - **Behavior:**
    - Requires `parameters` to be `UpdateDataPropertyPipelineParameters`, otherwise raises `ValueError`.
    - Fetches the subject graph and checks existing `(subject, predicate, ?o)` triples.
    - If no existing value: logs an error and returns an empty `Graph`.
    - If multiple existing values: logs an error and returns an empty `Graph`.
    - If exactly one value:
      - Removes the old triple and inserts the new one.
      - If predicate is `rdfs:label`, also inserts `(subject, skos:altLabel, new_literal)`.
    - Persists changes via `triple_store.insert(...)` and `triple_store.remove(...)`.
    - Returns the refreshed subject graph from the store.

- `UpdateDataPropertyPipeline.as_tools() -> list[langchain_core.tools.BaseTool]`
  - **Purpose:** Exposes the pipeline as a LangChain `StructuredTool` named `update_data_property`.

- `UpdateDataPropertyPipeline.as_api(...) -> None`
  - **Purpose:** API exposure hook; currently a no-op (returns `None` and does not register routes).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation in `UpdateDataPropertyPipelineConfiguration`.
- Internally uses `SPARQLUtils` and `ABIModule.get_instance().engine.services.triple_store` to read subject graphs.
- Uses `rdflib` types (`Graph`, `URIRef`, `Literal`) and vocabularies (`RDFS`, `SKOS`, `XSD`).

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
        subject_uri="http://ontology.naas.ai/abi/your-subject-id",
        predicate_uri=str(RDFS.label),
        object_new_value="Ford Motor Company",
        language="en",
    )
)

print(graph.serialize(format="turtle"))
```

## Caveats
- Update only succeeds when **exactly one** existing value is found for `(subject_uri, predicate_uri, ?o)`.
  - If **zero** or **multiple** values exist, it returns an **empty graph** and logs an error.
- `object_new_value` is typed as `str` in parameters; the runtime code contains branches for `float`/`int`, but typical validation will pass strings.
- When updating `rdfs:label`, the pipeline also inserts the same literal as `skos:altLabel`.
