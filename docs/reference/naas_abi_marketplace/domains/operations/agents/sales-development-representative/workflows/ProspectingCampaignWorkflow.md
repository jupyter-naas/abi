# ProspectingCampaignWorkflow

## What it is
- A **non-functional workflow template** for designing and executing a prospecting campaign in the Sales Development Representative domain.
- Provides a placeholder `execute()` implementation that returns planned steps and echoes received input keys.

## Public API
- `@dataclass ProspectingCampaignWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty; inherits from `WorkflowConfiguration`).

- `class ProspectingCampaignWorkflow(Workflow)`
  - `__init__(config: Optional[ProspectingCampaignWorkflowConfiguration] = None)`
    - Initializes the workflow with a provided config or a default configuration.
    - Emits a warning log indicating it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Logs a warning that it is not implemented.
    - Returns a dict containing:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `planned_steps`: list of step strings
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- Configuration:
  - `ProspectingCampaignWorkflowConfiguration` exists but defines no additional fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.sales-development-representative.workflows.ProspectingCampaignWorkflow import (
    ProspectingCampaignWorkflow,
)

async def main():
    wf = ProspectingCampaignWorkflow()
    result = await wf.execute({
        "campaign_objectives": {"goal": "increase meetings"},
        "target_personas": ["VP Sales", "Head of RevOps"],
        "messaging_framework": {"value_prop": "reduce tool sprawl"},
        "channel_strategy": ["email", "linkedin"],
    })
    print(result)

asyncio.run(main())
```

## Caveats
- The module explicitly states **NOT FUNCTIONAL YET**.
- `execute()` does not perform real workflow logic; it only returns a template response and planned steps.
