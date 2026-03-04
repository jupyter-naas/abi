# GenericWorkflow

## What it is
A generic workflow wrapper that:
- Renders a SPARQL query from a Jinja2 template and validated Pydantic parameters
- Executes the query via a `TripleStoreService`
- Converts results to a Python list using `SPARQLUtils`
- Exposes the workflow as a LangChain `StructuredTool`

## Public API
- `class GenericWorkflow(Generic[T])`
  - `__init__(name, description, sparql_template, arguments_model, triple_store_service)`
    - Stores workflow metadata, a SPARQL Jinja2 template, the Pydantic arguments model, and the triple store service.
  - `run(parameters: T)`
    - Renders `sparql_template` with `parameters.model_dump()`, executes the SPARQL query, and returns results as a list.
    - On any exception, returns `[{ "error": "<message>" }]`.
  - `as_tools() -> list[BaseTool]`
    - Returns a list containing a single `StructuredTool` that:
      - Validates kwargs using `arguments_model`
      - Calls `run()` with the constructed model instance

## Configuration/Dependencies
- **Pydantic**: `arguments_model` must be a subclass of `pydantic.BaseModel`.
- **Jinja2**: Imported inside `run()` (`from jinja2 import Template`) to render the SPARQL template.
- **Triple store**: Requires an instance of `naas_abi_core.services.triple_store.TripleStoreService.TripleStoreService` implementing `query(sparql_query)`.
- **Result conversion**: Uses `naas_abi_core.utils.SPARQL.SPARQLUtils(...).results_to_list(results)`.
- **LangChain tools**: Uses `langchain_core.tools.StructuredTool` / `BaseTool`.

## Usage
```python
from pydantic import BaseModel
from naas_abi_core.modules.templatablesparqlquery.workflows.GenericWorkflow import GenericWorkflow

# Define the validated inputs for the template
class Args(BaseModel):
    limit: int = 10

sparql_template = """
SELECT ?s ?p ?o WHERE {
  ?s ?p ?o .
}
LIMIT {{ limit }}
"""

# triple_store_service must be provided by your environment
workflow = GenericWorkflow(
    name="example_sparql_query",
    description="Runs a templated SPARQL query",
    sparql_template=sparql_template,
    arguments_model=Args,
    triple_store_service=triple_store_service,
)

result = workflow.run(Args(limit=5))
tools = workflow.as_tools()
```

## Caveats
- `run()` prints the rendered SPARQL query to stdout (`print(sparql_query)`).
- Errors are swallowed and returned as a list with an `"error"` dict, which may mask exceptions.
- The SPARQL template is rendered with Jinja2 using `parameters.model_dump()`; template variables must match model field names.
