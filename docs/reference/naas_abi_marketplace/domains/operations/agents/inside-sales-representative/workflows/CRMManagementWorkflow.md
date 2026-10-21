# CRMManagementWorkflow

## What it is
- A **non-functional workflow template** for CRM data management and optimization.
- Emits warnings indicating it is **not implemented yet** and returns a placeholder response.

## Public API
- `CRMManagementWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty; inherits base configuration behavior).
- `CRMManagementWorkflow(Workflow)`
  - `__init__(config: Optional[CRMManagementWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default configuration.
    - Logs a warning that this is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that execution is not implemented.
    - Returns a placeholder dict with:
      - `status: "template_only"`
      - `message`
      - `inputs_received` (list of input keys)
  - `get_workflow_description() -> str`
    - Returns a static description string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`.
- `CRMManagementWorkflowConfiguration` currently has **no custom fields**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.inside-sales representative.workflows.CRMManagementWorkflow import (
    CRMManagementWorkflow,
)

async def main():
    wf = CRMManagementWorkflow()
    result = await wf.execute({"account_id": "123", "action": "sync"})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform any CRM operations; it only returns a placeholder response and logs warnings.
