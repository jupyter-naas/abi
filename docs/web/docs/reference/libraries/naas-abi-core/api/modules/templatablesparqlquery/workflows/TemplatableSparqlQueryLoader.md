# TemplatableSparqlQueryLoader

## What it is
Loads “templatable” SPARQL queries from a `TripleStoreService`, builds Pydantic argument models for each query, and returns a list of `GenericWorkflow` instances ready to execute those templates with validated inputs.

## Public API
- `async_asyncio_thread_jobs(jobs)`
  - Runs a list of thread jobs concurrently using `asyncio.to_thread`.
  - Returns gathered results.
- `asyncio_thread_job(jobs)`
  - Synchronous wrapper around `async_asyncio_thread_jobs` using `asyncio.run`.
- `class TemplatableSparqlQueryLoader`
  - `__init__(triple_store_service: TripleStoreService)`
    - Stores the triple store service used to query metadata.
  - `templatable_queries() -> tuple[dict, dict]`
    - Queries the triple store for:
      - `intentMapping:TemplatableSparqlQuery` items (label, description, template, argument URIs)
      - `intentMapping:QueryArgument` items (name, description, validation pattern/format)
    - Returns:
      - `queries`: mapping of query URI → metadata dict including `hasArgument` list
      - `arguments`: mapping of argument URI → argument metadata
  - `load_workflows() -> list`
    - For each templatable query:
      - Creates a Pydantic model via `create_model(...)` with string fields for each argument.
      - Applies `Field(..., description=..., pattern=..., example=...)` based on argument metadata.
      - Instantiates `GenericWorkflow[ArgumentsModel](label, description, sparqlTemplate, ArgumentsModel, triple_store_service)`.
    - Returns a list of workflows; logs a warning and skips on per-query errors.

## Configuration/Dependencies
- Requires an instance of `naas_abi_core.services.triple_store.TripleStoreService.TripleStoreService` providing `.query(str)`.
- Uses:
  - `pydantic` (`Field`, `create_model`)
  - `rdflib` (`Graph`, `RDF`, `URIRef`) to locally query argument metadata
  - `naas_abi_core.logger` for warnings
  - Local `GenericWorkflow` class (imported from `.GenericWorkflow`)

## Usage
```python
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.modules.templatablesparqlquery.workflows.TemplatableSparqlQueryLoader import (
    TemplatableSparqlQueryLoader,
)

triple_store = TripleStoreService(...)  # must be configured for your environment
loader = TemplatableSparqlQueryLoader(triple_store)

workflows = loader.load_workflows()
for wf in workflows:
    print(wf)  # each is a GenericWorkflow parameterized by a generated Pydantic args model
```

## Caveats
- `load_workflows()` swallows any exception per query and only logs a warning; problematic queries may be silently skipped.
- Argument fields are always typed as `str` and marked required (`Field(...)`), with validation enforced via regex `pattern` from the triple store.
- The helper functions `async_asyncio_thread_jobs` / `asyncio_thread_job` are defined but not used by `TemplatableSparqlQueryLoader` in this file.
