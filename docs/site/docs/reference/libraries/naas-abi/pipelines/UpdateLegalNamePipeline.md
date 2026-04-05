# UpdateLegalNamePipeline

## What it is
- A pipeline that conditionally adds an `ABI.isLegalNameOf` relationship between a legal-name individual and an organization in an RDF triple store.
- Returns the updated RDF graph for the legal-name individual.

## Public API
- `UpdateLegalNamePipelineConfiguration(PipelineConfiguration)`
  - Fields:
    - `triple_store: ITripleStoreService` - triple store service used to fetch and insert RDF triples.
- `UpdateLegalNamePipelineParameters(PipelineParameters)`
  - Fields:
    - `individual_uri: str` - URI of the legal name individual (validated by `URI_REGEX`).
    - `organization_uri: Optional[str]` - organization URI to relate via `ABI.isLegalNameOf` (validated by `URI_REGEX`).
- `UpdateLegalNamePipeline(Pipeline)`
  - `__init__(configuration: UpdateLegalNamePipelineConfiguration)`
    - Stores configuration (notably the triple store service).
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Validates `parameters` type.
    - Loads the subject graph for `individual_uri`.
    - If `organization_uri` is provided and the triple does not already exist, inserts:
      - `(individual_uri, ABI.isLegalNameOf, organization_uri)`
    - Persists inserted triples to the triple store and returns the merged graph.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool` named `update_legal_name`.
  - `as_api(...) -> None`
    - Present but does not register any routes (no-op).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation providing at least:
  - `get_subject_graph(subject: rdflib.term.Identifier) -> rdflib.Graph`
  - `insert(graph: rdflib.Graph) -> None`
- Uses:
  - `rdflib.Graph`, `rdflib.URIRef`
  - Ontology constants: `ABI.isLegalNameOf`
  - Pydantic validation via `Field(..., pattern=URI_REGEX)`

## Usage
```python
from naas_abi.pipelines.UpdateLegalNamePipeline import (
    UpdateLegalNamePipeline,
    UpdateLegalNamePipelineConfiguration,
    UpdateLegalNamePipelineParameters,
)

# triple_store must be an ITripleStoreService implementation
config = UpdateLegalNamePipelineConfiguration(triple_store=triple_store)
pipeline = UpdateLegalNamePipeline(config)

params = UpdateLegalNamePipelineParameters(
    individual_uri="https://example.org/legal-name/123",
    organization_uri="https://example.org/org/456",
)

updated_graph = pipeline.run(params)
print(len(updated_graph))
```

### As a LangChain tool
```python
tool = pipeline.as_tools()[0]
result_graph = tool.run({
    "individual_uri": "https://example.org/legal-name/123",
    "organization_uri": "https://example.org/org/456",
})
```

## Caveats
- `run()` only accepts `UpdateLegalNamePipelineParameters`; passing any other `PipelineParameters` raises `ValueError`.
- If `organization_uri` is not provided, no changes are inserted.
- `as_api()` is implemented as a no-op; no API endpoint is exposed by this class.
