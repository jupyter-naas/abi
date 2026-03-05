# UpdateCommercialOrganizationPipeline

## What it is
A pipeline that updates RDF properties for an existing *commercial organization* individual in a triple store. It conditionally inserts missing triples (does not duplicate existing statements) and returns the updated RDF graph.

## Public API
- **`UpdateCommercialOrganizationPipelineConfiguration`** (`PipelineConfiguration`)
  - Holds dependencies for the pipeline.
  - Fields:
    - `triple_store: ITripleStoreService` — service used to read/insert RDF triples.

- **`UpdateCommercialOrganizationPipelineParameters`** (`PipelineParameters`)
  - Input schema (Pydantic-style annotations) for updates:
    - `individual_uri: str` (required) — URI of the commercial organization (validated by `URI_REGEX`).
    - `legal_uri: Optional[str]` — URI for legal name individual.
    - `ticker_uri: Optional[str]` — URI for ticker individual.
    - `website_uri: Optional[str]` — URI for website individual.
    - `linkedin_page_uri: Optional[str]` — URI for LinkedIn organization page individual.
    - `logo_url: Optional[str]` — logo URL literal (pattern `https?://.*`).

- **`UpdateCommercialOrganizationPipeline`** (`Pipeline`)
  - `__init__(configuration: UpdateCommercialOrganizationPipelineConfiguration)`
    - Constructs the pipeline with a triple store dependency.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Validates parameter type (`UpdateCommercialOrganizationPipelineParameters`).
    - Loads the subject graph for `individual_uri` from the triple store.
    - For each provided optional field, checks if the corresponding triple already exists; if not, adds it to an insert graph and inserts it into the triple store.
    - Returns the original graph merged with inserted triples.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes a LangChain `StructuredTool` named `update_commercial_organization` that calls `run(...)`.
  - `as_api(router: APIRouter, ...) -> None`
    - Present but currently does nothing (returns `None` without registering routes).

## Configuration/Dependencies
- Requires an implementation of **`ITripleStoreService`** with at least:
  - `get_subject_graph(subject: rdflib.term.URIRef) -> rdflib.Graph`
  - `insert(graph: rdflib.Graph) -> None`
- Uses RDF predicates from **`naas_abi_core.utils.Graph.ABI`**:
  - `ABI.hasLegalName`, `ABI.hasTickerSymbol`, `ABI.hasWebsite`, `ABI.hasLinkedInPage`, `ABI.logo`
- Input URI validation uses **`URI_REGEX`**.

## Usage
```python
from naas_abi.pipelines.UpdateCommercialOrganizationPipeline import (
    UpdateCommercialOrganizationPipeline,
    UpdateCommercialOrganizationPipelineConfiguration,
    UpdateCommercialOrganizationPipelineParameters,
)

# triple_store must implement ITripleStoreService
config = UpdateCommercialOrganizationPipelineConfiguration(triple_store=triple_store)
pipeline = UpdateCommercialOrganizationPipeline(config)

params = UpdateCommercialOrganizationPipelineParameters(
    individual_uri="http://example.org/org/123",
    legal_uri="http://example.org/legalname/abc",
    website_uri="http://example.org/website/xyz",
    logo_url="https://cdn.example.org/logo.png",
)

updated_graph = pipeline.run(params)
```

## Caveats
- `run()` only **inserts** missing triples; it does **not** remove or overwrite existing values.
- `as_api(...)` is a no-op in this implementation (no HTTP endpoints are registered).
- `run()` raises `ValueError` if `parameters` is not an `UpdateCommercialOrganizationPipelineParameters` instance.
