# AgentRecommendationWorkflow

## What it is
A `Workflow` implementation that:
- Loads templated SPARQL queries from a Turtle (`.ttl`) file.
- Matches a natural-language intent to a query template.
- Templates and executes the query against an Oxigraph SPARQL endpoint.
- Formats results into a list of agent recommendations.
- Exposes the workflow as a LangChain `StructuredTool`.

## Public API

### Classes

- `AgentRecommendationConfiguration(WorkflowConfiguration)`
  - Holds runtime dependencies and file/endpoint locations.
  - Fields:
    - `triple_store: ITripleStoreService` (present but not used in this module)
    - `oxigraph_url: str` (default: `http://localhost:7878`)
    - `queries_file_path: str` (default: `src/core/modules/abi/ontologies/application-level/AgentRecommendationSparqlQueries.ttl`)

- `AgentRecommendationParameters(WorkflowParameters)`
  - Input parameters for recommendations.
  - Fields:
    - `intent_description: str` (required)
    - `min_intelligence_score: Optional[int] = 10`
    - `max_input_cost: Optional[float] = None`
    - `max_results: Optional[int] = 10`
    - `provider_preference: Optional[str] = None`

- `AgentRecommendationWorkflow(Workflow)`
  - Main workflow class.
  - `__init__(configuration: AgentRecommendationConfiguration)`
    - Loads SPARQL query templates from `queries_file_path`.
  - `run_workflow(parameters: WorkflowParameters) -> Dict[str, Any]`
    - Validates parameter type (`AgentRecommendationParameters` only).
    - Selects a query by keyword matching on `intent_description`.
    - Replaces `{{ var }}` placeholders and processes `{% if var %}...{% endif %}` blocks.
    - Executes query via HTTP POST to `"{oxigraph_url}/query"`.
    - Returns:
      - `intent`, `query_used`, `recommendations`, `total_found`
  - `as_tools() -> list[BaseTool]`
    - Returns a LangChain `StructuredTool` named `recommend_ai_agents` that calls `run_workflow`.
  - `as_api(...) -> None`
    - Present but currently does nothing and always returns `None`.
  - `get_configuration() -> AgentRecommendationConfiguration`
    - Returns the workflow configuration.

## Configuration/Dependencies

### Runtime dependencies
- SPARQL endpoint: Oxigraph accessible at `configuration.oxigraph_url` (expects `POST /query` returning JSON in SPARQL results format).
- Query templates file: `configuration.queries_file_path` must exist and be parseable as Turtle.
  - Extracts entries where the graph has subjects with predicate `INTENT_MAPPING.intentDescription`.
  - For each such subject, it reads:
    - `INTENT_MAPPING.intentDescription`
    - `INTENT_MAPPING.sparqlTemplate`

### Python packages used
- `requests` (HTTP calls)
- `rdflib` (parsing TTL query file)
- `langchain_core.tools` (tool wrapper)

## Usage

### Run the workflow directly
```python
from naas_abi.workflows.AgentRecommendationWorkflow import (
    AgentRecommendationWorkflow,
    AgentRecommendationConfiguration,
    AgentRecommendationParameters,
)

# triple_store is required by the configuration type but not used by this workflow.
dummy_triple_store = object()

wf = AgentRecommendationWorkflow(
    AgentRecommendationConfiguration(
        triple_store=dummy_triple_store,  # must be provided
        oxigraph_url="http://localhost:7878",
        queries_file_path="path/to/AgentRecommendationSparqlQueries.ttl",
    )
)

out = wf.run_workflow(
    AgentRecommendationParameters(
        intent_description="Need help writing a business proposal",
        min_intelligence_score=50,
        max_results=5,
    )
)

print(out["total_found"])
print(out["recommendations"][:1])
```

### Use as a LangChain tool
```python
tools = wf.as_tools()
result = tools[0].invoke({"intent_description": "fast coding assistant", "max_results": 3})
print(result["recommendations"])
```

## Caveats
- The `.ttl` queries file must exist; otherwise initialization raises `FileNotFoundError`.
- Intent matching is keyword-based with a fixed mapping; unmatched intents default to the “business proposal” query.
- Template substitution is plain string replacement for `{{ key }}` plus a basic regex-based `{% if var %}` handler (no loops/advanced templating).
- `as_api(...)` is a stub and does not register any routes.
- `triple_store` is required in configuration but is not used in this module.
