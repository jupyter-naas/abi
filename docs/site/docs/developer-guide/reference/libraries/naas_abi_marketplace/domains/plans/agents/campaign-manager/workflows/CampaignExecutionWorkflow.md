# CampaignExecutionWorkflow

## What it is
- A **non-functional workflow template** intended for campaign execution and coordination.
- Emits warnings indicating it is **not implemented yet**.

## Public API
- `CampaignExecutionWorkflowConfiguration(WorkflowConfiguration)`
  - Placeholder configuration dataclass (no fields defined).
- `CampaignExecutionWorkflow(Workflow)`
  - `__init__(config: Optional[CampaignExecutionWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default configuration.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that execution is not implemented.
    - Returns a template response including received input keys.
  - `get_workflow_description() -> str`
    - Returns a static description string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs.
  - `naas_abi_core.workflow.workflow.Workflow` base class.
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration` base configuration class.
- Configuration:
  - `CampaignExecutionWorkflowConfiguration` currently contains **no configurable fields**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.campaign_manager.workflows.CampaignExecutionWorkflow import (
    CampaignExecutionWorkflow,
)

async def main():
    wf = CampaignExecutionWorkflow()
    result = await wf.execute({"campaign_id": "123", "dry_run": True})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**:
  - `execute()` does not perform campaign actions; it only returns a template response.
  - Initialization and execution emit warning logs.
