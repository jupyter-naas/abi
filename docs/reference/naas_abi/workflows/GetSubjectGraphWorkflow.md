# GetSubjectGraphWorkflow

## What it is
- A workflow that retrieves the **subject graph** for a given RDF individual/instance URI from a configured triple store.
- Returns the graph serialized as **Turtle** (`text/turtle`) in a single string.

## Public API

### Classes
- `GetSubjectGraphWorkflowConfiguration(WorkflowConfiguration)`
  - Workflow configuration placeholder (no additional fields).

- `GetSubjectGraphWorkflowParameters(WorkflowParameters)`
  - Input parameters:
    - `uri: str` (required) — URI of the individual; validated against `URI_REGEX`.
    - `depth: int` (optional, default `2`) — traversal depth for the subject graph.

- `GetSubjectGraphWorkflow(Workflow)`
  - `__init__(configuration: GetSubjectGraphWorkflowConfiguration)`
    - Initializes SPARQL utilities using `ABIModule.get_instance().engine.services.triple_store`.
  - `get_subject_graph(parameters: GetSubjectGraphWorkflowParameters) -> str`
    - Fetches the subject graph via `SPARQLUtils.get_subject_graph(uri, depth)` and serializes it to Turtle.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool` named `get_subject_graph` with `GetSubjectGraphWorkflowParameters` as the argument schema.
  - `as_api(router: APIRouter, ...) -> None`
    - Present but does not register any routes (returns `None`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi.ABIModule` singleton providing `engine.services.triple_store`.
  - `naas_abi_core.utils.SPARQL.SPARQLUtils` for graph retrieval.
  - `langchain_core.tools.StructuredTool` for tool exposure.
  - `pydantic.Field` / `typing.Annotated` for parameter schema and validation.
  - `URI_REGEX` for URI format validation.

## Usage

```python
from naas_abi.workflows.GetSubjectGraphWorkflow import (
    GetSubjectGraphWorkflow,
    GetSubjectGraphWorkflowConfiguration,
    GetSubjectGraphWorkflowParameters,
)

wf = GetSubjectGraphWorkflow(GetSubjectGraphWorkflowConfiguration())

params = GetSubjectGraphWorkflowParameters(
    uri="http://ontology.naas.ai/abi/a25ef0cc-56cf-458a-88c0-fabccb69e9b7",
    depth=2,
)

turtle = wf.get_subject_graph(params)
print(turtle)
```

Using as a LangChain tool:

```python
wf = GetSubjectGraphWorkflow(GetSubjectGraphWorkflowConfiguration())
tool = wf.as_tools()[0]

result = tool.run({
    "uri": "http://ontology.naas.ai/abi/a25ef0cc-56cf-458a-88c0-fabccb69e9b7",
    "depth": 2,
})
print(result)
```

## Caveats
- `as_api(...)` is a no-op in this implementation (no API routes are created).
- Requires a working `ABIModule` instance with an available `triple_store`; otherwise initialization or graph retrieval will fail.
