# UpdateLinkedInPagePipeline

## What it is
- A pipeline that updates RDF triples for a LinkedIn page resource in an ontology.
- It reads the existing subject graph from a triple store and inserts missing triples for:
  - LinkedIn identifiers/URLs
  - Ownership relations between the LinkedIn page and an owner entity

## Public API

### Classes

- `UpdateLinkedInPagePipelineConfiguration(PipelineConfiguration)`
  - **Purpose:** Provide required services to the pipeline.
  - **Fields:**
    - `triple_store: ITripleStoreService` - triple store used to read and insert RDF triples.

- `UpdateLinkedInPagePipelineParameters(PipelineParameters)`
  - **Purpose:** Input schema for updates (Pydantic-compatible).
  - **Fields:**
    - `individual_uri: str` - URI of the LinkedIn page (must match `URI_REGEX`).
    - `linkedin_id: Optional[str]` - LinkedIn unique ID.
    - `linkedin_url: Optional[str]` - LinkedIn URL (with LinkedIn ID as identifier).
    - `linkedin_public_id: Optional[str]` - LinkedIn public ID.
    - `linkedin_public_url: Optional[str]` - must match `https?://.+\.linkedin\.com/(in|company|school|showcase)/[^?]+`
    - `owner_uri: Optional[str]` - URI of the owner (must match `URI_REGEX`).

- `UpdateLinkedInPagePipeline(Pipeline)`
  - **Purpose:** Orchestrates the update and persistence of missing triples.
  - **Methods:**
    - `__init__(configuration: UpdateLinkedInPagePipelineConfiguration)`
      - Stores configuration (notably `triple_store`).
    - `run(parameters: PipelineParameters) -> rdflib.Graph`
      - Validates parameters type (`UpdateLinkedInPagePipelineParameters` required).
      - Loads the current subject graph for `individual_uri`.
      - Inserts only triples that do not already exist with the exact same object value.
      - If `owner_uri` is provided, inserts both:
        - `(individual_uri, ABI.isLinkedInPageOf, owner_uri)`
        - `(owner_uri, ABI.hasLinkedInPage, individual_uri)`
      - Persists inserts via `triple_store.insert(graph_insert)`.
      - Returns the merged graph (`existing + inserted`).
    - `as_tools() -> list[langchain_core.tools.BaseTool]`
      - Exposes a LangChain `StructuredTool` named `update_linkedin_page` that calls `run(...)`.
    - `as_api(...) -> None`
      - Present but does nothing (returns `None`; no routes are registered).

## Configuration/Dependencies
- Requires an implementation of `ITripleStoreService` providing:
  - `get_subject_graph(subject_uri: str) -> rdflib.Graph`
  - `insert(graph: rdflib.Graph) -> None`
- Uses RDF/ontology terms from `naas_abi_core.utils.Graph.ABI`:
  - `ABI.linkedin_id`, `ABI.linkedin_url`, `ABI.linkedin_public_id`, `ABI.linkedin_public_url`
  - `ABI.isLinkedInPageOf`, `ABI.hasLinkedInPage`
- Uses `rdflib` for graph operations (`Graph`, `URIRef`, `Literal`).
- Parameter validation relies on Pydantic `Field` constraints (e.g., URL pattern, URI regex).

## Usage

```python
from naas_abi.pipelines.UpdateLinkedInPagePipeline import (
    UpdateLinkedInPagePipeline,
    UpdateLinkedInPagePipelineConfiguration,
    UpdateLinkedInPagePipelineParameters,
)

# triple_store must implement ITripleStoreService
config = UpdateLinkedInPagePipelineConfiguration(triple_store=triple_store)

pipeline = UpdateLinkedInPagePipeline(config)

params = UpdateLinkedInPagePipelineParameters(
    individual_uri="https://example.org/linkedin/page/123",
    linkedin_public_url="https://www.linkedin.com/company/acme-inc",
    owner_uri="https://example.org/org/acme",
)

graph = pipeline.run(params)
```

Using the LangChain tool wrapper:

```python
tool = UpdateLinkedInPagePipeline(config).as_tools()[0]
result_graph = tool.run({
    "individual_uri": "https://example.org/linkedin/page/123",
    "linkedin_id": "123",
})
```

## Caveats
- `run()` only inserts a triple if an *identical* triple (same subject, predicate, and object literal/URI) is not already present; it does not remove or replace existing differing values.
- `as_api()` is a no-op; it does not expose any HTTP endpoints.
