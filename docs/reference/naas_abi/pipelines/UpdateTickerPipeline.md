# UpdateTickerPipeline

## What it is
- A `Pipeline` that updates a ticker symbol individual in an RDF triple store.
- Currently supports adding (if missing) the `ABI.isTickerSymbolOf` relationship from a ticker to an organization.

## Public API
- `UpdateTickerPipelineConfiguration`
  - Fields:
    - `triple_store: ITripleStoreService` — triple store service used to read and write RDF graphs.

- `UpdateTickerPipelineParameters` (Pydantic model)
  - `individual_uri: str` — URI of the ticker individual (validated by `URI_REGEX`).
  - `organization_uri: Optional[str]` — URI of the organization to link (validated by `URI_REGEX`).

- `UpdateTickerPipeline(configuration)`
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Validates parameter type (`UpdateTickerPipelineParameters` required).
    - Fetches the existing subject graph for `individual_uri`.
    - If `organization_uri` is provided and the triple does not already exist, inserts:
      - `(individual_uri, ABI.isTickerSymbolOf, organization_uri)`
    - Writes inserts via `triple_store.insert(...)` and returns the updated graph.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes a LangChain `StructuredTool` named `update_ticker` that calls `run(...)`.
  - `as_api(...) -> None`
    - Present but does nothing (returns `None` and does not register routes).

## Configuration/Dependencies
- Requires an implementation of `ITripleStoreService` providing at least:
  - `get_subject_graph(subject: rdflib.term.URIRef) -> rdflib.Graph`
  - `insert(graph: rdflib.Graph) -> None`
- Uses:
  - `rdflib.Graph`, `rdflib.URIRef`
  - `naas_abi_core.utils.Graph.ABI` (for `ABI.isTickerSymbolOf`)
  - `URI_REGEX` for URI validation in parameters
  - `langchain_core.tools.StructuredTool` for tool exposure

## Usage
```python
from rdflib import URIRef
from naas_abi.pipelines.UpdateTickerPipeline import (
    UpdateTickerPipeline,
    UpdateTickerPipelineConfiguration,
    UpdateTickerPipelineParameters,
)

# Provide a triple store service that implements ITripleStoreService
triple_store = ...  # ITripleStoreService

pipeline = UpdateTickerPipeline(
    UpdateTickerPipelineConfiguration(triple_store=triple_store)
)

result_graph = pipeline.run(
    UpdateTickerPipelineParameters(
        individual_uri="http://ontology.naas.ai/abi/ticker/ABC",
        organization_uri="http://ontology.naas.ai/abi/org/SomeOrganization",
    )
)

print(len(result_graph))
```

## Caveats
- `run()` raises `ValueError` if `parameters` is not an `UpdateTickerPipelineParameters` instance.
- `as_api()` is a no-op; no HTTP routes are created.
- The pipeline only *adds* the `isTickerSymbolOf` triple when missing; it does not remove or replace existing relationships.
