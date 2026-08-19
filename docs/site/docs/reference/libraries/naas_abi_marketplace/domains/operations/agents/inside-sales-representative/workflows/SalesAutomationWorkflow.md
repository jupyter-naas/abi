# SalesAutomationWorkflow

## What it is
- A **non-functional workflow template** intended for sales process automation and efficiency.
- Logs warnings on initialization and execution to indicate it is not implemented.

## Public API
- `SalesAutomationWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow.
  - Currently has **no additional fields** beyond `WorkflowConfiguration`.

- `SalesAutomationWorkflow(Workflow)`
  - `__init__(config: Optional[SalesAutomationWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default `SalesAutomationWorkflowConfiguration`.
    - Emits a warning: workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Emits a warning: not implemented.
    - Returns a template response:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Sales process automation and efficiency workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- `SalesAutomationWorkflowConfiguration` currently does not define any workflow-specific parameters.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.inside-sales representative.workflows.SalesAutomationWorkflow import (
    SalesAutomationWorkflow,
)

async def main():
    wf = SalesAutomationWorkflow()
    result = await wf.execute({"lead_id": "123", "priority": "high"})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not implement real automation; it only returns a placeholder payload and logs warnings.
