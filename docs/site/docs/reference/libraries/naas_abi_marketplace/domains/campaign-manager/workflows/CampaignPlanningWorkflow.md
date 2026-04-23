# CampaignPlanningWorkflow

## What it is
- A **non-functional workflow template** for a “Comprehensive campaign planning and strategy” process.
- Logs warnings on initialization and execution to indicate it is not implemented.

## Public API
- `CampaignPlanningWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow.
  - Currently has **no additional fields** beyond `WorkflowConfiguration`.

- `CampaignPlanningWorkflow(Workflow)`
  - `__init__(config: Optional[CampaignPlanningWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided configuration or a default configuration.
    - Emits a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Emits a warning that execution is not implemented.
    - Returns a stub response:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Comprehensive campaign planning and strategy workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- `CampaignPlanningWorkflowConfiguration` currently does not define custom configuration parameters.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.campaign-manager.workflows.CampaignPlanningWorkflow import (
    CampaignPlanningWorkflow,
)

async def main():
    wf = CampaignPlanningWorkflow()
    result = await wf.execute({"goal": "awareness", "budget": 1000})
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform planning; it only returns a template stub response and logs warnings.
