# EngagementCampaignWorkflow

## What it is
- A **non-functional workflow template** for a community engagement campaign planning process.
- Provides placeholder behavior: logs warnings and returns a structured “template_only” response.

## Public API
- `@dataclass EngagementCampaignWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty; inherits from `WorkflowConfiguration`).

- `class EngagementCampaignWorkflow(Workflow)`
  - `__init__(config: Optional[EngagementCampaignWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided configuration or a default configuration.
    - Emits a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Placeholder execution method.
    - Returns a dict with:
      - `status`: `"template_only"`
      - `message`: `"�� Workflow not functional yet"` (note: contains replacement characters)
      - `planned_steps`: list of template step descriptions
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string of the workflow’s intent.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as the workflow base types
- Configuration:
  - `EngagementCampaignWorkflowConfiguration` currently has no custom fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.community_manager.workflows.EngagementCampaignWorkflow import (
    EngagementCampaignWorkflow,
)

async def main():
    wf = EngagementCampaignWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"topic": "campaign"},
            "context": {"audience": "community"},
            "parameters": {"duration_days": 7},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform real processing; it only returns template metadata and logs a warning.
- The returned `message` contains replacement characters (`"��"`), which may be an encoding artifact.
