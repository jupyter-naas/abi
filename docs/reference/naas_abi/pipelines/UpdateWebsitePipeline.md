# UpdateWebsitePipeline

## What it is
A pipeline that updates a **Website** individual in an RDF triple store by optionally linking it to an owner via ontology predicates.

## Public API
- **`UpdateWebsitePipelineConfiguration`** (`PipelineConfiguration`)
  - Purpose: Holds dependencies required by the pipeline.
  - Fields:
    - `triple_store: ITripleStoreService` — triple store service used to insert RDF graphs.

- **`UpdateWebsitePipelineParameters`** (`PipelineParameters`)
  - Purpose: Input parameters for the update operation.
  - Fields:
    - `individual_uri: str` — website URI; must match `URI_REGEX` and **must start with** `http://ontology.naas.ai/abi/`.
    - `owner_uri: Optional[str] = None` — optional owner URI (validated by `URI_REGEX`).

- **`UpdateWebsitePipeline`** (`Pipeline`)
  - Purpose: Builds an RDF graph with the requested changes and inserts it into the configured triple store.
  - Methods:
    - `__init__(configuration: UpdateWebsitePipelineConfiguration)`
    - `run(parameters: PipelineParameters) -> rdflib.Graph`
      - Validates parameter type and website URI prefix.
      - If `owner_uri` is provided, adds:
        - `(website_uri, ABI.isWebsiteOf, owner_uri)`
        - `(owner_uri, ABI.hasWebsite, website_uri)`
      - Inserts the resulting graph via `configuration.triple_store.insert(graph)`.
    - `as_tools() -> list[langchain_core.tools.BaseTool]`
      - Exposes the pipeline as a LangChain `StructuredTool` named **`update_website`**.
    - `as_api(...) -> None`
      - Present but does not register any routes (returns `None`).

## Configuration/Dependencies
- Requires an implementation of **`ITripleStoreService`** that provides:
  - `insert(graph: rdflib.Graph) -> ...` (called to persist changes)
- Uses:
  - `rdflib.Graph`, `rdflib.URIRef`
  - `naas_abi_core.utils.Graph.ABI` predicates (`ABI.isWebsiteOf`, `ABI.hasWebsite`)
  - `URI_REGEX` for Pydantic validation

## Usage
```python
from rdflib import Graph

from naas_abi.pipelines.UpdateWebsitePipeline import (
    UpdateWebsitePipeline,
    UpdateWebsitePipelineConfiguration,
    UpdateWebsitePipelineParameters,
)

class DummyTripleStore:
    def insert(self, graph: Graph):
        # Replace with a real triple store implementation
        print(f"Inserting {len(graph)} triples")

pipeline = UpdateWebsitePipeline(
    UpdateWebsitePipelineConfiguration(triple_store=DummyTripleStore())
)

params = UpdateWebsitePipelineParameters(
    individual_uri="http://ontology.naas.ai/abi/website/123",
    owner_uri="http://ontology.naas.ai/abi/owner/456",
)

result_graph = pipeline.run(params)
print(len(result_graph))
```

## Caveats
- `individual_uri` must start with **`http://ontology.naas.ai/abi/`** or `run()` raises `ValueError`.
- `as_api()` is a no-op and does not expose an HTTP endpoint.
- Duplicate-checking for owner triples is performed against the **newly created graph**, so it will always add the owner triples when `owner_uri` is provided.
