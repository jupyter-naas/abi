# ResourceManagementWorkflow

## What it is
- A **non-functional workflow template** for *resource allocation and capacity planning* in the project-manager domain.
- Provides a placeholder `execute()` implementation that returns a structured “template_only” response and logs warnings.

## Public API

### `ResourceManagementWorkflowConfiguration`
- Dataclass extending `naas_abi_core.workflow.workflow.WorkflowConfiguration`.
- Currently has **no additional fields** (placeholder configuration).

### `ResourceManagementWorkflow`
Workflow class extending `naas_abi_core.workflow.workflow.Workflow`.

- `__init__(config: Optional[ResourceManagementWorkflowConfiguration] = None)`
  - Initializes the workflow with the provided config or a default `ResourceManagementWorkflowConfiguration`.
  - Logs a warning that the workflow is not functional yet.

- `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
  - Template execution method (not implemented).
  - Logs a warning and returns:
    - `status`: `"template_only"`
    - `message`: non-functional notice
    - `planned_steps`: list of planned workflow steps (strings)
    - `inputs_received`: list of keys from `inputs`

- `get_workflow_description() -> str`
  - Returns a multi-line description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration object:
  - `ResourceManagementWorkflowConfiguration` (currently empty)

## Usage

```python
import asyncio

from naas_abi_marketplace.domains.project-manager.workflows.ResourceManagementWorkflow import (
    ResourceManagementWorkflow,
)

async def main():
    wf = ResourceManagementWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"example": True},
            "context": {"team": "A"},
            "parameters": {"mode": "dry-run"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does not perform real resource management; it only returns a template response and planned steps.
