# PerformanceManagementWorkflow

## What it is
- A **non-functional (template-only)** workflow for employee performance management in the human resources domain.
- Logs warnings indicating it is not implemented yet.
- Returns a stub response describing planned steps and echoing received input keys.

## Public API

### `PerformanceManagementWorkflowConfiguration`
- `class PerformanceManagementWorkflowConfiguration(WorkflowConfiguration)`
  - Purpose: Placeholder configuration type for the workflow.
  - Fields: None (inherits from `WorkflowConfiguration`).

### `PerformanceManagementWorkflow`
- `class PerformanceManagementWorkflow(Workflow)`
  - Purpose: Template workflow implementation.

#### `__init__(config: Optional[PerformanceManagementWorkflowConfiguration] = None)`
- Initializes the workflow with the provided config, or a default `PerformanceManagementWorkflowConfiguration`.
- Emits a warning via `naas_abi_core.logger` that the workflow is template-only.

#### `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
- Template execution method (not implemented).
- Emits a warning that execution is not implemented.
- Returns a dict with:
  - `status`: `"template_only"`
  - `message`: `"🚧 Workflow not functional yet"`
  - `planned_steps`: list of placeholder steps
  - `inputs_received`: list of keys from `inputs`

#### `get_workflow_description() -> str`
- Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` (used for warnings)
- Configuration:
  - `PerformanceManagementWorkflowConfiguration` exists but has no custom fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.human-resources-manager.workflows.PerformanceManagementWorkflow import (
    PerformanceManagementWorkflow,
)

async def main():
    wf = PerformanceManagementWorkflow()
    result = await wf.execute({"domain_specific_input": "example", "context": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform real processing; it returns a stub response and planned steps.
