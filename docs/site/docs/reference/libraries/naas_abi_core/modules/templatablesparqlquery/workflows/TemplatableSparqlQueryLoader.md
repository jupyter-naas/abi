# TemplatableSparqlQueryLoader

## What it is
- Loads *templatable SPARQL query* definitions and their *argument metadata* from a triple store.
- Produces a list of `GenericWorkflow` instances, each paired with a generated Pydantic model that validates the query arguments.

## Public API

### Functions
- `async_asyncio_thread_jobs(jobs)`
  - Asynchronously runs a list of `asyncio.to_thread(*job)` calls and gathers results.
- `asyncio_thread_job(jobs)`
  - Synchronous wrapper that runs `async_asyncio_thread_jobs(jobs)` via `asyncio.run`.

### Class: `TemplatableSparqlQueryLoader`
- `__init__(triple_store_service: TripleStoreService)`
  - Stores a `TripleStoreService` used to query the triple store.
- `templatable_queries() -> tuple[dict, dict]`
  - Queries the triple store for:
    - `intentMapping:TemplatableSparqlQuery` entries (label, description, template, and argument URIs)
    - `intentMapping:QueryArgument` entries (name, description, validation pattern/format)
  - Returns:
    - `queries`: mapping `{query_uri: {label, description, sparqlTemplate, hasArgument: [argument_uri...]}}`
    - `arguments`: mapping `{argument_uri: {name, description, validationPattern, validationFormat}}`
- `load_workflows() -> list`
  - Builds one `GenericWorkflow[...]` per templatable query.
  - For each query:
    - Dynamically creates a Pydantic model named `"{LabelCapitalized}Arguments"`.
    - Each argument becomes a required `str` field with:
      - `description` from `argumentDescription`
      - `pattern` from `validationPattern`
      - `example` from `validationFormat`
  - Returns a list of created workflows; failures are logged as warnings and skipped.

## Configuration/Dependencies
- Requires a working `TripleStoreService` instance providing `.query(sparql: str)` returning iterable rows.
- SPARQL schema expectations (must exist in the triple store):
  - `intentMapping:TemplatableSparqlQuery`
    - `rdfs:label`
    - `intentMapping:intentDescription`
    - `intentMapping:sparqlTemplate`
    - `intentMapping:hasArgument`
  - `intentMapping:QueryArgument`
    - `intentMapping:argumentName`
    - `intentMapping:argumentDescription`
    - `intentMapping:validationPattern`
    - `intentMapping:validationFormat`
- Uses:
  - `pydantic.create_model`, `pydantic.Field` for runtime model generation
  - `rdflib.Graph` for local querying of argument metadata
  - `naas_abi_core.logger` for warnings

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
    print(wf)
```

## Caveats
- If any query/argument is missing expected properties (e.g., `validationPattern`), workflow creation can fail and will be skipped with a warning.
- The generated Pydantic fields are all typed as `str` and marked required (`Field(...)`), regardless of `validationFormat`.
- `async_asyncio_thread_jobs` / `asyncio_thread_job` are defined but not used by `load_workflows()`.
