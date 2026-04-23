# EditorialPlanningWorkflow

## What it is
- A **non-functional workflow template** for editorial calendar and content planning in the *content-strategist* domain.
- Provides placeholder structure and returns a stub response indicating it is not implemented.

## Public API
- `EditorialPlanningWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow.
  - Currently contains **no custom fields**.

- `EditorialPlanningWorkflow(Workflow)`
  - `__init__(config: Optional[EditorialPlanningWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided configuration or a default one.
    - Emits a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Stub executor.
    - Returns a dictionary with:
      - `status: "template_only"`
      - `message`
      - `planned_steps` (a list of template steps)
      - `inputs_received` (list of input keys)
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `EditorialPlanningWorkflowConfiguration` extends `WorkflowConfiguration` but adds no fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content_strategist.workflows.EditorialPlanningWorkflow import (
    EditorialPlanningWorkflow,
)

async def main():
    wf = EditorialPlanningWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"topic": "AI in marketing"},
            "context": {"audience": "B2B"},
            "parameters": {"horizon_weeks": 4},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform real planning; it only returns placeholder content and logs a warning.
