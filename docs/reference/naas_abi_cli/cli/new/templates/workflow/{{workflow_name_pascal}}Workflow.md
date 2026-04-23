# `{{workflow_name_pascal}}Workflow`

## What it is
- A template workflow module defining:
  - A configuration dataclass (`{{workflow_name_pascal}}WorkflowConfiguration`)
  - A parameters model (`{{workflow_name_pascal}}WorkflowParameters`)
  - A workflow implementation (`{{workflow_name_pascal}}Workflow`) with integrations for LangChain tools and (stubbed) API exposure.

## Public API
- `@dataclass {{workflow_name_pascal}}WorkflowConfiguration(WorkflowConfiguration)`
  - Purpose: Holds workflow configuration (currently empty template).

- `class {{workflow_name_pascal}}WorkflowParameters(WorkflowParameters)`
  - Purpose: Defines validated input parameters for the workflow (currently empty template).
  - Notes: Contains a commented example showing how to declare typed parameters using `Annotated` and `pydantic.Field`.

- `class {{workflow_name_pascal}}Workflow(Workflow[{{workflow_name_pascal}}WorkflowParameters])`
  - `__init__(configuration: {{workflow_name_pascal}}WorkflowConfiguration)`
    - Purpose: Initialize the workflow with its configuration.
  - `run(parameters: {{workflow_name_pascal}}WorkflowParameters) -> dict | list[dict]`
    - Purpose: Execute workflow logic (currently `pass`; must be implemented).
  - `as_tools() -> list[BaseTool]`
    - Purpose: Expose the workflow as a LangChain `StructuredTool` named `{{workflow_name_pascal}}`.
    - Behavior: Wraps `run()` and builds `{{workflow_name_pascal}}WorkflowParameters` from tool kwargs.
  - `as_api(router: APIRouter, route_name: str = "", name: str = "", description: str = "", description_stream: str = "", tags: list[str | Enum] | None = None) -> None`
    - Purpose: Placeholder for exposing workflow as API routes.
    - Behavior: Ensures `tags` is a list when `None`, then returns `None` without registering routes.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow` (`Workflow`, `WorkflowConfiguration`, `WorkflowParameters`)
  - `langchain_core.tools` (`BaseTool`, `StructuredTool`) for tool exposure
  - `naas_abi_core.utils.Expose.APIRouter` for API exposure (currently unused in implementation)
  - `pydantic.Field` and `typing.Annotated` for parameter schema definitions (example is commented)
- Imports present but not used in this template:
  - `Optional`, `ITripleStoreService`

## Usage
Minimal example (requires implementing `run()` to be functional):

```python
# from your_module import (
#     {{workflow_name_pascal}}Workflow,
#     {{workflow_name_pascal}}WorkflowConfiguration,
#     {{workflow_name_pascal}}WorkflowParameters,
# )

cfg = {{workflow_name_pascal}}WorkflowConfiguration()
wf = {{workflow_name_pascal}}Workflow(cfg)

params = {{workflow_name_pascal}}WorkflowParameters()
result = wf.run(params)  # currently not implemented in template
```

Using as a LangChain tool:

```python
cfg = {{workflow_name_pascal}}WorkflowConfiguration()
wf = {{workflow_name_pascal}}Workflow(cfg)

tool = wf.as_tools()[0]
# tool(**kwargs) will call wf.run({{workflow_name_pascal}}WorkflowParameters(**kwargs))
```

## Caveats
- `run()` is not implemented (`pass`); calling it will not produce output until you add logic.
- `as_api()` does not register any routes; it only normalizes `tags` and returns `None`.
- `{{workflow_name_pascal}}WorkflowParameters` currently defines no fields; tool invocation will accept no structured inputs unless you add them.
