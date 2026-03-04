# SearchIndividualWorkflow

## What it is
- A workflow that searches ontology **NamedIndividuals** in a triple store using SPARQL.
- Matches against `rdfs:label` and `skos:altLabel`, then ranks results using fuzzy matching (`thefuzz`).

## Public API
- `SearchIndividualWorkflowConfiguration`
  - `triple_store: ITripleStoreService`: triple store service used to execute SPARQL queries.

- `SearchIndividualWorkflowParameters`
  - `search_label: str` (required): label text to search for.
  - `class_uri: Optional[str]` (default `None`): if provided, restricts results to individuals of this class (`?individual_uri a <class_uri>`).
  - `limit: Optional[int]` (default `10`): maximum results to return (1–100).
  - `query: Optional[str]` (default `None`): custom SPARQL query; if provided, it replaces the generated query.

- `SearchIndividualWorkflow(configuration: SearchIndividualWorkflowConfiguration)`
  - `search_individual(parameters: SearchIndividualWorkflowParameters) -> list[dict]`
    - Executes a SPARQL query and returns a list of dicts containing result bindings (notably `individual_uri`, `label`) plus a computed `score` (fuzzy match).
    - Sorts by `score` descending and de-duplicates by `individual_uri`.
  - `as_tools() -> list[BaseTool]`
    - Exposes `search_individual` as a LangChain `StructuredTool` named `"search_individual"`.
  - `as_api(...) -> None`
    - Present but does not register any routes (returns `None`).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation with a `.query(sparql_query: str)` method returning iterable `rdflib.query.ResultRow`.
- Uses:
  - `rdflib` result rows (`rdflib.query.ResultRow`)
  - `thefuzz.fuzz.token_set_ratio` for scoring
  - `naas_abi_core.utils.String.normalize` for normalization
  - LangChain (`langchain_core.tools.StructuredTool`)

## Usage
```python
from naas_abi.workflows.SearchIndividualWorkflow import (
    SearchIndividualWorkflow,
    SearchIndividualWorkflowConfiguration,
    SearchIndividualWorkflowParameters,
)

# triple_store must implement ITripleStoreService and provide .query(str) -> iterable of ResultRow
config = SearchIndividualWorkflowConfiguration(triple_store=triple_store)
wf = SearchIndividualWorkflow(config)

params = SearchIndividualWorkflowParameters(
    search_label="Naas.ai",
    class_uri=None,
    limit=10,
)

results = wf.search_individual(params)
print(results)
```

Using as a LangChain tool:
```python
tool = wf.as_tools()[0]
out = tool.run(search_label="Naas.ai", limit=5)
print(out)
```

## Caveats
- The default generated SPARQL query references `owl:NamedIndividual`, `rdfs:label`, and `skos:altLabel` but does not declare prefixes; it relies on the triple store/query engine environment handling these.
- `query` parameter fully overrides the generated SPARQL; in that case, returned bindings (and presence of `label`) depend on the custom query, which affects scoring/sorting behavior.
