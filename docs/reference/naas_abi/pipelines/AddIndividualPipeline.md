# AddIndividualPipeline

## What it is
- A pipeline that adds a named individual (instance) to an RDF triple store.
- Before inserting, it searches for an existing individual with a similar label in the target class; if found above a threshold, it returns that individual’s graph instead of creating a new one.

## Public API
- `AddIndividualPipelineConfiguration`
  - Configuration container for the pipeline.
  - Fields:
    - `triple_store: ITripleStoreService` — triple store service used to fetch/insert RDF graphs.
    - `search_individual_configuration: SearchIndividualWorkflowConfiguration` — configuration for the search workflow.

- `AddIndividualPipelineParameters`
  - Input parameters schema:
    - `individual_label: str` — label for the individual to add.
    - `class_uri: str` — URI of the class the individual is an instance of.
    - `threshold: Optional[int] = 80` — minimum search score (0–100) to treat an existing individual as a match.

- `AddIndividualPipeline`
  - `__init__(configuration: AddIndividualPipelineConfiguration)`
    - Creates the pipeline and internally instantiates `SearchIndividualWorkflow`.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Validates parameters type (`AddIndividualPipelineParameters` required).
    - Searches for existing individuals in `class_uri` by `individual_label`.
    - If a match is found with `score >= threshold`, returns `triple_store.get_subject_graph(individual_uri)`.
    - Otherwise:
      - Creates a new individual under the `http://ontology.naas.ai/abi/` namespace with a UUID.
      - Adds triples:
        - `(individual_uri, rdf:type, owl:NamedIndividual)`
        - `(individual_uri, rdf:type, <class_uri>)`
        - `(individual_uri, rdfs:label, "individual_label")`
      - Inserts the graph into the triple store and returns it.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Returns multiple `StructuredTool` wrappers for LangChain:
      - `add_individual_to_triple_store` (generic: requires `class_uri` + `individual_label`)
      - Specialized helpers with preset `class_uri`:
        - `add_commercial_organization`
        - `add_person`
        - `add_website`
        - `add_skill`
        - `add_legal_name`
        - `add_ticker_symbol`
        - `add_linkedin_page`
  - `as_api(...) -> None`
    - Present but does not register any routes (returns `None`).

## Configuration/Dependencies
- Depends on:
  - `ITripleStoreService` (must implement at least `insert(graph)` and `get_subject_graph(subject_uri)`).
  - `SearchIndividualWorkflow` and its configuration (`SearchIndividualWorkflowConfiguration`).
  - `rdflib` for RDF graph construction.
  - `langchain_core.tools.StructuredTool` for tool wrappers.

## Usage
```python
from naas_abi.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
)

# Provide concrete implementations/configurations from your environment:
triple_store = ...  # ITripleStoreService
search_cfg = ...    # SearchIndividualWorkflowConfiguration

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

print(len(g))  # number of triples returned/created
```

## Caveats
- `run()` only accepts `AddIndividualPipelineParameters`; other `PipelineParameters` will raise `ValueError`.
- Matching behavior depends on the search workflow result structure containing at least `score` and `individual_uri`.
- If `threshold` is `None`, no search results will pass the filter and a new individual will always be created.
