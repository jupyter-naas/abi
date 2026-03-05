# AddIndividualPipeline

## What it is
A pipeline that adds a named individual (instance) to an RDF triple store, or returns an existing matching individual if one is already present (based on a search workflow and score threshold).

## Public API
- `AddIndividualPipelineConfiguration(PipelineConfiguration)` (dataclass)
  - Purpose: Provide dependencies for the pipeline.
  - Fields:
    - `triple_store: ITripleStoreService` — triple store service used to insert and fetch graphs.
    - `search_individual_configuration: SearchIndividualWorkflowConfiguration` — configuration passed to `SearchIndividualWorkflow`.

- `AddIndividualPipelineParameters(PipelineParameters)` (Pydantic model)
  - Purpose: Input parameters for adding/searching an individual.
  - Fields:
    - `individual_label: str` — label for the individual (stored as `rdfs:label`).
    - `class_uri: str` — class URI the individual will be typed as.
    - `threshold: Optional[int] = 80` — score threshold (0–100) to accept an existing individual from search results.

- `AddIndividualPipeline(Pipeline)`
  - `__init__(configuration: AddIndividualPipelineConfiguration)`
    - Purpose: Initialize pipeline and internal `SearchIndividualWorkflow`.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Purpose:
      - Searches for an existing individual matching `individual_label` within `class_uri`.
      - If a match is found with `score >= threshold`, returns the subject graph from the triple store.
      - Otherwise, creates a new individual with a UUID-based ABI URI, inserts it into the triple store, and returns the created graph.
    - Raises:
      - `ValueError` if `parameters` is not `AddIndividualPipelineParameters`.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Purpose: Exposes the pipeline as LangChain `StructuredTool`s:
      - `add_individual_to_triple_store` (generic: requires `class_uri` and `individual_label`)
      - Convenience tools that pre-fill `class_uri`:
        - `add_commercial_organization`
        - `add_person`
        - `add_website`
        - `add_skill`
        - `add_legal_name`
        - `add_ticker_symbol`
        - `add_linkedin_page`
  - `as_api(...) -> None`
    - Purpose: Present but not implemented (always returns `None` and does not register routes).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation providing:
  - `insert(graph: rdflib.Graph) -> ...`
  - `get_subject_graph(subject_uri: str) -> rdflib.Graph`
- Uses `SearchIndividualWorkflow` from `naas_abi.workflows.SearchIndividualWorkflow`:
  - Called via `search_individual(...)` with `class_uri` and `search_label`.
  - Expects results containing `score` and `individual_uri`.
- RDF libraries/terms:
  - Builds an `rdflib.Graph`, binds namespaces (`bfo`, `cco`, `abi`, `dcterms`), and adds triples:
    - `(individual_uri, rdf:type, owl:NamedIndividual)`
    - `(individual_uri, rdf:type, <class_uri>)`
    - `(individual_uri, rdfs:label, "label")`
- Namespaces used:
  - `ABI = "http://ontology.naas.ai/abi/"`
  - `CCO = "https://www.commoncoreontologies.org/"`
  - `BFO = "http://purl.obolibrary.org/obo/"`

## Usage
```python
from naas_abi.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
)
from naas_abi.workflows.SearchIndividualWorkflow import SearchIndividualWorkflowConfiguration

# Provide concrete implementations/configuration from your environment:
triple_store = ...  # must implement ITripleStoreService
search_cfg = SearchIndividualWorkflowConfiguration(...)

pipeline = AddIndividualPipeline(
    AddIndividualPipelineConfiguration(
        triple_store=triple_store,
        search_individual_configuration=search_cfg,
    )
)

g = pipeline.run(
    AddIndividualPipelineParameters(
        individual_label="Naas.ai",
        class_uri="https://www.commoncoreontologies.org/ont00000443",
        threshold=80,
    )
)

print(len(g), "triples")
```

Using the LangChain tools:
```python
tools = pipeline.as_tools()
add_person = next(t for t in tools if t.name == "add_person")
result_graph = add_person.run({"individual_label": "Ada Lovelace"})
```

## Caveats
- Search filtering only runs when `threshold` is not `None`. If `threshold=None`, no search result will be accepted and a new individual will always be created.
- When multiple matches exceed the threshold, the first result is used.
- `as_api` is a no-op (no routes are exposed).
