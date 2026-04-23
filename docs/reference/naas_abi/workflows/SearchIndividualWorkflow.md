# SearchIndividualWorkflow

## What it is
- A `Workflow` that searches for ontology individuals in a triple store by label.
- Builds and runs a SPARQL query against a configured `ITripleStoreService`, then ranks results using fuzzy matching.

## Public API

### Classes

- `SearchIndividualWorkflowConfiguration(WorkflowConfiguration)`
  - **Purpose:** Provides required dependencies.
  - **Fields:**
    - `triple_store: ITripleStoreService` — service used to execute SPARQL queries.

- `SearchIndividualWorkflowParameters(WorkflowParameters)`
  - **Purpose:** Input parameters for the search operation.
  - **Fields:**
    - `search_label: str` — label to search for (required).
    - `class_uri: Optional[str]` — optional class URI filter.
    - `limit: Optional[int]` — max number of results (default `10`, `1..100`).
    - `query: Optional[str]` — optional custom SPARQL query to use instead of the generated one.

- `SearchIndividualWorkflow(Workflow)`
  - **Purpose:** Executes the search and exposes it as a LangChain tool.

### Methods

- `SearchIndividualWorkflow.search_individual(parameters: SearchIndividualWorkflowParameters) -> list[dict]`
  - Executes a SPARQL query (generated unless `parameters.query` is provided).
  - Returns a list of dicts derived from query rows (e.g., `individual_uri`, `label`) plus:
    - `score`: fuzzy match score between the normalized search label and the returned label.
  - Post-processing:
    - sorts results by `score` descending
    - removes duplicate `individual_uri` entries

- `SearchIndividualWorkflow.as_tools() -> list[BaseTool]`
  - Returns a LangChain `StructuredTool` named `search_individual` that calls `search_individual(...)`.

- `SearchIndividualWorkflow.as_api(...) -> None`
  - Present but currently does nothing (always returns `None`).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation via `SearchIndividualWorkflowConfiguration.triple_store`.
- Uses:
  - `naas_abi_core.utils.String.normalize` to normalize labels for fuzzy scoring and some query paths.
  - `thefuzz.fuzz.token_set_ratio` for scoring.
  - `rdflib.query.ResultRow` rows returned from the triple store query.

## Usage

```python
from naas_abi.workflows.SearchIndividualWorkflow import (
    SearchIndividualWorkflow,
    SearchIndividualWorkflowConfiguration,
    SearchIndividualWorkflowParameters,
)

# triple_store must implement ITripleStoreService and provide .query(sparql_query: str)
config = SearchIndividualWorkflowConfiguration(triple_store=triple_store)

wf = SearchIndividualWorkflow(config)

params = SearchIndividualWorkflowParameters(
    search_label="Naas.ai",
    class_uri=None,
    limit=10,
)

results = wf.search_individual(params)
print(results)  # list of dicts, including "individual_uri", "label", and "score" when label is present
```

Using as a LangChain tool:

```python
tools = wf.as_tools()
tool = tools[0]
out = tool.run({"search_label": "Naas.ai", "limit": 5})
print(out)
```

## Caveats
- `as_api(...)` is a no-op; no API routes are registered.
- If `parameters.query` is provided, it fully replaces the generated SPARQL query (including `limit` and `class_uri` behavior).
- Fuzzy `score` is only added when a `label` value is present in a result row; sorting treats missing scores as `0`.
