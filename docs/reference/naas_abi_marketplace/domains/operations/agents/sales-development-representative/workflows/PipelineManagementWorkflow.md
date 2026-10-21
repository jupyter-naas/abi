# PipelineManagementWorkflow

## What it is
- A **non-functional template** workflow intended for **sales pipeline management and optimization** in the Sales Development Representative domain.
- Logs warnings indicating it is **not implemented yet** and returns a placeholder response.

## Public API
- `@dataclass PipelineManagementWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty).

- `class PipelineManagementWorkflow(Workflow)`
  - `__init__(config: Optional[PipelineManagementWorkflowConfiguration] = None)`
    - Initializes the workflow with a configuration (defaults to an empty `PipelineManagementWorkflowConfiguration`).
    - Emits a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - **Does not perform real processing**; returns a placeholder payload including planned steps and received input keys.
    - Expected input keys (documented in docstring):
      - `pipeline_data`
      - `stage_definitions`
      - `conversion_metrics`
      - `forecast_parameters`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` base class.
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration` base configuration class.
- Configuration:
  - `PipelineManagementWorkflowConfiguration` currently has **no fields** (inherits from `WorkflowConfiguration`).

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.sales-development-representative.workflows.PipelineManagementWorkflow import (
    PipelineManagementWorkflow,
)

async def main():
    wf = PipelineManagementWorkflow()
    result = await wf.execute(
        {
            "pipeline_data": {},
            "stage_definitions": {},
            "conversion_metrics": {},
            "forecast_parameters": {},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` only returns:
  - `status: "template_only"`
  - `message` indicating it is not functional
  - `planned_steps` (static list)
  - `inputs_received` (list of provided input keys)
