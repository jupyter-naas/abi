# AgentRecommendationWorkflow

## What it is
A workflow that recommends AI agents (models/providers) based on a natural-language intent by:
- selecting a SPARQL query template from a TTL file,
- templating it with user constraints (scores, cost, provider, result limit),
- executing it against an Oxigraph SPARQL endpoint,
- formatting the bindings into a structured list of recommendations.

## Public API

### Classes

- `AgentRecommendationConfiguration(WorkflowConfiguration)`
  - Purpose: Configure where to load SPARQL templates from and where to execute them.
  - Fields:
    - `triple_store: ITripleStoreService` (currently not used in this module’s logic)
    - `oxigraph_url: str` (default: `http://localhost:7878`)
    - `queries_file_path: str` (default: `src/core/modules/abi/ontologies/application-level/AgentRecommendationSparqlQueries.ttl`)

- `AgentRecommendationParameters(WorkflowParameters)`
  - Purpose: Provide runtime inputs for generating recommendations.
  - Fields:
    - `intent_description: str` (required)
    - `min_intelligence_score: Optional[int]` (default: `10`)
    - `max_input_cost: Optional[float]` (default: `None`)
    - `max_results: Optional[int]` (default: `10`)
    - `provider_preference: Optional[str]` (default: `None`)

- `AgentRecommendationWorkflow(Workflow)`
  - Purpose: Load query templates, match intent, execute SPARQL, and return recommendations.

### Methods (AgentRecommendationWorkflow)

- `__init__(configuration: AgentRecommendationConfiguration)`
  - Loads query templates from `queries_file_path` at initialization.

- `run_workflow(parameters: WorkflowParameters) -> Dict[str, Any]`
  - Executes the end-to-end recommendation process.
  - Returns a dict with:
    - `intent`
    - `query_used` (the matched template’s intent description)
    - `recommendations` (list of formatted recommendations)
    - `total_found`

- `as_tools() -> list[BaseTool]`
  - Exposes the workflow as a LangChain `StructuredTool`:
    - name: `recommend_ai_agents`
    - args schema: `AgentRecommendationParameters`

- `as_api(...) -> None`
  - Present but does nothing (returns `None`).

- `get_configuration() -> AgentRecommendationConfiguration`
  - Returns the workflow configuration.

## Configuration/Dependencies

### External services
- **Oxigraph SPARQL endpoint**: the workflow POSTs queries to:
  - `POST {oxigraph_url}/query`
  - Header: `Content-Type: application/sparql-query`
  - Expects a JSON response shaped like SPARQL results (`results.bindings`).

### Files
- **TTL file with SPARQL templates**: `queries_file_path` must exist.
  - Parsed via `rdflib.Graph.parse(..., format="turtle")`.
  - Query templates are extracted using the `INTENT_MAPPING` predicates:
    - `intentMapping:intentDescription`
    - `intentMapping:sparqlTemplate`

### Python dependencies (imports used)
- `requests`
- `rdflib`
- `langchain_core.tools` (`BaseTool`, `StructuredTool`)
- `naas_abi_core` workflow and router types

## Usage

```python
from naas_abi.workflows.AgentRecommendationWorkflow import (
    AgentRecommendationWorkflow,
    AgentRecommendationConfiguration,
    AgentRecommendationParameters,
)

# Provide a triple_store instance per your environment (not used by this workflow logic).
triple_store = ...  # must satisfy ITripleStoreService

wf = AgentRecommendationWorkflow(
    AgentRecommendationConfiguration(
        triple_store=triple_store,
        oxigraph_url="http://localhost:7878",
        queries_file_path="path/to/AgentRecommendationSparqlQueries.ttl",
    )
)

result = wf.run_workflow(
    AgentRecommendationParameters(
        intent_description="Need a fast and cheap model for coding",
        min_intelligence_score=50,
        max_input_cost=1.0,
        max_results=5,
        provider_preference=None,
    )
)

print(result["total_found"])
print(result["recommendations"][:1])
```

Using as a LangChain tool:

```python
tool = wf.as_tools()[0]
output = tool.invoke({"intent_description": "Write a business proposal"})
print(output["recommendations"])
```

## Caveats

- The workflow **prints** progress logs directly to stdout.
- `queries_file_path` must exist; otherwise `FileNotFoundError` is raised during initialization.
- Intent matching is keyword-based and selects among fixed query IDs:
  - `abi#findBusinessProposalAgents` (default fallback)
  - `abi#findCodingAgents`
  - `abi#findMathAgents`
  - `abi#findFastestAgents`
  - `abi#findBestValueAgents`
  Missing IDs in the loaded TTL will cause `KeyError` at runtime when selected.
- Template substitution is simple string replacement for `{{ key }}` plus a basic `{% if var %}...{% endif %}` processor; more complex templating is not supported.
- `max_input_cost` and `provider_preference` are only applied if the SPARQL template includes corresponding placeholders/conditionals; otherwise they have no effect.
