# ContentPlanningWorkflow

## What it is
- A **non-functional workflow template** for “strategic content planning and ideation”.
- Provides a placeholder `execute()` implementation that returns a structured template response and logs warnings.

## Public API
- `@dataclass ContentPlanningWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for `ContentPlanningWorkflow`.
  - Currently has **no additional fields** beyond the base `WorkflowConfiguration`.

- `class ContentPlanningWorkflow(Workflow)`
  - `__init__(config: Optional[ContentPlanningWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided configuration or a default one.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Returns a dict including:
      - `status`: `"template_only"`
      - `message`: indicates not functional
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of keys from `inputs`
    - Logs a warning that execution is not implemented.
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` base classes.
- Configuration:
  - `ContentPlanningWorkflowConfiguration` is required by the base `Workflow`, but currently does not add any settings.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content_creator.workflows.ContentPlanningWorkflow import (
    ContentPlanningWorkflow,
)

async def main():
    wf = ContentPlanningWorkflow()
    result = await wf.execute({"context": {"audience": "developers"}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform real planning/ideation; it only returns a template response and logs warnings.
