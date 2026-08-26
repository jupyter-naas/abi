# BudgetManagementWorkflow

## What it is
- A **non-functional workflow template** for campaign budget allocation and management.
- Emits warnings on initialization and execution to indicate it is not implemented.

## Public API
- `BudgetManagementWorkflowConfiguration(WorkflowConfiguration)`
  - Placeholder configuration dataclass (no fields defined).
- `BudgetManagementWorkflow(Workflow)`
  - `__init__(config: Optional[BudgetManagementWorkflowConfiguration] = None)`
    - Initializes the workflow with a provided configuration or a default one.
    - Logs a warning that the workflow is a template only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that execution is not implemented.
    - Returns a template response containing:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Campaign budget allocation and management workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- Configuration:
  - `BudgetManagementWorkflowConfiguration` currently defines **no custom parameters**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.campaign_manager.workflows.BudgetManagementWorkflow import (
    BudgetManagementWorkflow,
)

async def main():
    wf = BudgetManagementWorkflow()
    result = await wf.execute({"campaign_id": "123", "budget": 1000})
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not perform any budget logic; it only returns a static template response and logs warnings.
