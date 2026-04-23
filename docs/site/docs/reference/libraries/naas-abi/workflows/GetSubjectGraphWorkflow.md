# GetSubjectGraphWorkflow

## What it is
- A workflow that retrieves the **subject graph** (RDF subgraph rooted at a given subject URI) from a configured triple store and returns it serialized as **Turtle**.

## Public API
- **`GetSubjectGraphWorkflowConfiguration`** (`WorkflowConfiguration`)
  - Workflow configuration container (no custom fields).

- **`GetSubjectGraphWorkflowParameters`** (`WorkflowParameters`)
  - Input parameters:
    - `uri: str` - URI of the individual/instance (validated with `URI_REGEX`).
    - `depth: int = 2` - Traversal depth for the subject graph.

- **`GetSubjectGraphWorkflow`** (`Workflow`)
  - `__init__(configuration: GetSubjectGraphWorkflowConfiguration)`
    - Initializes SPARQL utilities using `ABIModule.get_instance().engine.services.triple_store`.
  - `get_subject_graph(parameters: GetSubjectGraphWorkflowParameters) -> str`
    - Returns the subject graph serialized in Turtle (`format="turtle"`).
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool` named `get_subject_graph` that accepts the parameters schema and returns Turtle text.
  - `as_api(router: APIRouter, ...) -> None`
    - Present but currently does not register any routes (returns `None`).

## Configuration/Dependencies
- Depends on:
  - `ABIModule.get_instance().engine.services.triple_store` (triple store service)
  - `SPARQLUtils.get_subject_graph(uri, depth)` (graph retrieval)
  - LangChain `StructuredTool` for tool exposure
  - Pydantic `Field` and `URI_REGEX` for parameter validation

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

## Caveats
- `as_api(...)` is a no-op: it does not expose HTTP endpoints.
- Requires a properly initialized `ABIModule` with an available `triple_store`; otherwise workflow initialization/use will fail.
