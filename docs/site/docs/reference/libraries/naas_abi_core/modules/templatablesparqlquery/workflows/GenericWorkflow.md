# GenericWorkflow

## What it is
- A small, generic workflow wrapper that:
  - Renders a SPARQL query from a Jinja2 template using a Pydantic model as parameters.
  - Executes the query via a `TripleStoreService`.
  - Converts query results to a Python list via `SPARQLUtils`.
- Can be exposed as a LangChain `StructuredTool`.

## Public API

### `class GenericWorkflow(Generic[T])`
Generic over `T`, where `T` is a `pydantic.BaseModel`.

#### `__init__(name, description, sparql_template, arguments_model, triple_store_service)`
- Stores metadata, a SPARQL Jinja2 template, the Pydantic argument model, and the triple-store client/service.

Parameters:
- `name: str` — tool/workflow name.
- `description: str` — tool/workflow description.
- `sparql_template: str` — Jinja2 template string for the SPARQL query.
- `arguments_model: Type[T]` — Pydantic model class defining accepted parameters.
- `triple_store_service: TripleStoreService` — service used to run SPARQL queries.

#### `run(parameters: T)`
- Renders `sparql_template` with `parameters.model_dump()`.
- Prints the rendered SPARQL query.
- Runs `triple_store_service.query(sparql_query)`.
- Returns `SPARQLUtils(triple_store_service).results_to_list(results)`.
- On any exception, returns a single-item list: `[{ "error": "<message>" }]`.

#### `as_tools() -> list[BaseTool]`
- Returns a one-item list containing a `langchain_core.tools.StructuredTool`:
  - `name` and `description` from the workflow
  - `args_schema` set to `arguments_model`
  - `func` calls `run(self.arguments_model(**kwargs))`

## Configuration/Dependencies
- **Pydantic**: parameters must be an instance of a `BaseModel` subclass; `model_dump()` is used.
- **Jinja2**: imported inside `run()` (`from jinja2 import Template`) to render the SPARQL string.
- **TripleStoreService**: must provide a `.query(sparql_query)` method.
- **SPARQLUtils**: must provide `.results_to_list(results)`.
- **LangChain Core**: `StructuredTool` and `BaseTool` are used for tool exposure.

## Usage

```python
from pydantic import BaseModel

# Define the arguments schema
class QueryArgs(BaseModel):
    subject: str

# Assume you have a real TripleStoreService instance
triple_store_service = ...  # TripleStoreService

sparql_template = """
SELECT ?p ?o WHERE {
  <{{ subject }}> ?p ?o .
}
LIMIT 10
"""

wf = GenericWorkflow(
    name="describe_subject",
    description="Fetch predicates/objects for a subject IRI",
    sparql_template=sparql_template,
    arguments_model=QueryArgs,
    triple_store_service=triple_store_service,
)

result = wf.run(QueryArgs(subject="http://example.org/resource/1"))
print(result)

# Expose as a LangChain tool
tools = wf.as_tools()
```

## Caveats
- `run()` **prints** the rendered SPARQL query to stdout.
- Any exception is swallowed and returned as `[{ "error": "..."}]`, so failures are not raised.
- The SPARQL is rendered via Jinja2 templating; input values are inserted into the template as provided.
