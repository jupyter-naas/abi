# `{{workflow_name_pascal}}Workflow`

## What it is
- A workflow template module defining:
  - A configuration dataclass
  - A parameters schema
  - A workflow class that can be exposed as a LangChain tool
- Intended to be filled in with workflow logic by implementing `run(...)`.

## Public API
- `{{workflow_name_pascal}}WorkflowConfiguration(WorkflowConfiguration)`
  - Workflow configuration container (currently empty; inherits base configuration behavior).

- `{{workflow_name_pascal}}WorkflowParameters(WorkflowParameters)`
  - Workflow parameters model (currently empty; example field definition is commented out).

- `{{workflow_name_pascal}}Workflow(Workflow[{{workflow_name_pascal}}WorkflowParameters])`
  - `__init__(configuration: {{workflow_name_pascal}}WorkflowConfiguration)`
    - Initializes the workflow with the provided configuration.
  - `run(parameters: {{workflow_name_pascal}}WorkflowParameters) -> dict | list[dict]`
    - Placeholder for workflow execution logic (`pass`).
  - `as_tools() -> list[BaseTool]`
    - Returns a single `StructuredTool` that calls `run(...)` with arguments parsed into `{{workflow_name_pascal}}WorkflowParameters`.
  - `as_api(...) -> None`
    - API exposure hook accepting an `APIRouter` and metadata fields; currently does nothing (returns `None`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.Workflow`, `WorkflowConfiguration`, `WorkflowParameters`
  - `langchain_core.tools.StructuredTool` / `BaseTool` for tool exposure
  - `naas_abi_core.utils.Expose.APIRouter` for API exposure (stubbed)
  - `pydantic.Field` and `typing.Annotated` (only used in commented example)
- Imports present but unused in this template:
  - `Optional`
  - `ITripleStoreService`

## Usage
```python
# Minimal usage (requires implementing run() to do anything meaningful)

cfg = {{workflow_name_pascal}}WorkflowConfiguration()
wf = {{workflow_name_pascal}}Workflow(cfg)

# Direct invocation (currently returns None because run() is pass)
result = wf.run({{workflow_name_pascal}}WorkflowParameters())
print(result)

# Tool exposure (LangChain)
tools = wf.as_tools()
tool = tools[0]
out = tool.run({})  # kwargs parsed into {{workflow_name_pascal}}WorkflowParameters
print(out)
```

## Caveats
- `run(...)` is not implemented; as provided, it returns `None`.
- `as_api(...)` is a stub and does not register any routes.
- The tool created by `as_tools()` uses `lambda **kwargs` and will fail validation if you add required fields to `{{workflow_name_pascal}}WorkflowParameters` but do not supply them.
