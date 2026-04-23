# RemoveIndividualPipeline

## What it is
A pipeline that removes an RDF individual from one or more named graphs in a triple store by:
- querying all triples where the given URI appears as subject or object,
- saving those triples to object storage as a Turtle file, and
- deleting the triples from the triple store.

## Public API

- `RemoveIndividualPipelineConfiguration`
  - `triple_store: ITripleStoreService`: triple store service used for SPARQL querying and removal.
  - `datastore_path: str = "knowledge_graph/remove"`: base path (in object storage) where removed triples are saved.

- `RemoveIndividualPipelineParameters`
  - `uri: str`: the URI (individual) to remove.
  - `graph_names: list[str]`: list of graph URIs to remove the individual from.

- `RemoveIndividualPipeline(configuration)`
  - `get_all_triples_for_uri(uri: str, graph_uri: str)`
    - Runs a SPARQL query against `graph_uri` to fetch all triples where `uri` is subject or object.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Removes matching triples from each graph in `parameters.graph_names`.
    - Saves removed triples to object storage under `{datastore_path}/{graph_name}/{local_uri}.ttl`.
    - Returns a combined `rdflib.Graph` containing all removed triples.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool` named `remove_individuals`.
  - `as_api(...) -> None`
    - Currently a no-op (does not register any routes).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation that supports:
  - `query(sparql: str)` returning iterable rows (`rdflib.query.ResultRow`-like).
  - `remove(graph: rdflib.Graph, graph_name: rdflib.term.URIRef)`.
- Uses object storage via:
  - `ABIModule.get_instance().engine.services.object_storage`
  - `StorageUtils.save_triples(graph, output_dir, filename)`
- Uses `rdflib.Graph` for assembling triples to remove.

## Usage

```python
from naas_abi.pipelines.RemoveIndividualPipeline import (
    RemoveIndividualPipeline,
    RemoveIndividualPipelineConfiguration,
    RemoveIndividualPipelineParameters,
)

# Provide an ITripleStoreService implementation from your environment
triple_store = ...  # ITripleStoreService

pipeline = RemoveIndividualPipeline(
    RemoveIndividualPipelineConfiguration(triple_store=triple_store)
)

removed = pipeline.run(
    RemoveIndividualPipelineParameters(
        uri="http://example.org/individual/123",
        graph_names=["http://example.org/graphs/mygraph"],
    )
)

print(f"Removed {len(removed)} triples")
```

## Caveats
- `graph_names` entries are treated as graph URIs; a `graph_name` directory is derived from the last path segment (`graph_uri.split('/')[-1]`).
- If no triples are found for a graph, nothing is removed and nothing is saved for that graph.
- `as_api()` is intentionally empty and does not expose HTTP endpoints.
