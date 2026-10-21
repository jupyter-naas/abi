# LeadGenerationWorkflow

## What it is
- A **non-functional workflow template** for multi-channel lead generation and sourcing in the Sales Development Representative domain.
- Provides a placeholder `execute()` implementation that returns a template response and logs warnings.

## Public API
- **`LeadGenerationWorkflowConfiguration(WorkflowConfiguration)`**
  - Dataclass configuration container for the workflow (currently empty; inherits base configuration).

- **`LeadGenerationWorkflow(Workflow)`**
  - **`__init__(config: Optional[LeadGenerationWorkflowConfiguration] = None)`**
    - Initializes the workflow with a provided configuration or a default `LeadGenerationWorkflowConfiguration`.
    - Logs a warning that the workflow is not functional yet.
  - **`async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`**
    - Template execution method; logs a warning and returns a dict with:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of planned workflow steps (strings)
      - `inputs_received`: list of input keys received
  - **`get_workflow_description() -> str`**
    - Returns a descriptive multi-line string about the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `LeadGenerationWorkflowConfiguration` currently adds no fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.sales-development-representative.workflows.LeadGenerationWorkflow import (
    LeadGenerationWorkflow,
)

async def main():
    wf = LeadGenerationWorkflow()
    result = await wf.execute({
        "target_market": "B2B SaaS in EU",
        "ideal_customer_profile": {"company_size": "50-200", "role": "Sales Ops"},
        "lead_sources": ["LinkedIn", "Website"],
        "campaign_parameters": {"goal": "book meetings"},
    })
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not perform lead generation; it only returns a template payload and planned steps.
- Logs warnings on initialization and execution.
