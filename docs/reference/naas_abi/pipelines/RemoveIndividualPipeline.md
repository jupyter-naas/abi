# RemoveIndividualPipeline

## What it is
A pipeline that removes one or more RDF individuals from a triple store by:
- querying all triples where each URI appears as **subject or object**
- persisting the removed triples to object storage as Turtle files
- deleting those triples from the triple store
- returning a combined `rdflib.Graph` of all removed triples

## Public API

- `RemoveIndividualPipelineConfiguration(PipelineConfiguration)`
  - **Fields**
    - `triple_store: ITripleStoreService` — triple store service used for SPARQL query and removal
    - `datastore_path: str = "datastore/ontology/removed_individual"` — output path used when saving removed triples

- `RemoveIndividualPipelineParameters(PipelineParameters)`
  - **Fields**
    - `uris_to_remove: List[str]` — list of URIs to remove (`min_items=1`)

- `RemoveIndividualPipeline(Pipeline)`
  - `__init__(configuration: RemoveIndividualPipelineConfiguration)`
    - Initializes pipeline and `StorageUtils` using `ABIModule.get_instance().engine.services.object_storage`.
  - `get_all_triples_for_uri(uri: str)`
    - Runs a SPARQL `SELECT ?s ?p ?o` query returning all triples where `uri` is the subject or the object.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Removes triples for each URI in `parameters.uris_to_remove`, saves removed triples to storage, deletes them from the triple store, and returns a combined graph of removed triples.
  - `as_tools() -> list[BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool` named `remove_individuals`.
  - `as_api(...) -> None`
    - Present but currently does nothing (returns `None`).

## Configuration/Dependencies

- Requires:
  - `ITripleStoreService` with:
    - `query(sparql: str)` returning iterable rows `(s, p, o)`
    - `remove(graph: rdflib.Graph)` to delete triples
  - `ABIModule` engine initialized with:
    - `services.object_storage` (used by `StorageUtils`)
    - typically also `services.triple_store` used to populate configuration
- Uses `rdflib.Graph` and binds namespaces: `bfo`, `cco`, `abi`.
- Saves each removed URI’s triples to:
  - directory: `RemoveIndividualPipelineConfiguration.datastore_path`
  - filename: `<last_path_segment_of_uri>.ttl`

## Usage

```python
from naas_abi import ABIModule
from naas_abi_core.engine.Engine import Engine
from naas_abi.pipelines.RemoveIndividualPipeline import (
    RemoveIndividualPipeline,
    RemoveIndividualPipelineConfiguration,
    RemoveIndividualPipelineParameters,
)

# Boot engine and load module providing ABIModule services
engine = Engine()
engine.load(module_names=["naas_abi"])

triple_store_service = ABIModule.get_instance().engine.services.triple_store

pipeline = RemoveIndividualPipeline(
    RemoveIndividualPipelineConfiguration(triple_store=triple_store_service)
)

removed = pipeline.run(
    RemoveIndividualPipelineParameters(
        uris_to_remove=[
            "http://ontology.naas.ai/abi/example-uri-1",
            "http://ontology.naas.ai/abi/example-uri-2",
        ]
    )
)

print(removed.serialize(format="turtle"))
```

## Caveats

- `run()` only accepts `RemoveIndividualPipelineParameters`; otherwise it raises `ValueError`.
- Output filenames are derived from `uri.split('/')[-1]`; URIs without a stable last path segment may lead to unexpected filenames.
- `as_api()` is a no-op (no routes are registered).
