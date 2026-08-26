# LeadQualificationWorkflow

## What it is
- A **non-functional workflow template** for lead qualification and scoring in the Sales Development Representative domain.
- Implements a `Workflow` with a placeholder `execute()` method that returns a template response and logs warnings.

## Public API
- `@dataclass LeadQualificationWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow.
  - Currently has **no additional fields** beyond `WorkflowConfiguration`.

- `class LeadQualificationWorkflow(Workflow)`
  - `__init__(config: Optional[LeadQualificationWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided configuration (or a default one).
    - Emits a warning indicating the workflow is a template only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Placeholder execution method.
    - Logs a warning and returns:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of planned step descriptions
      - `inputs_received`: list of input keys provided
  - `get_workflow_description() -> str`
    - Returns a multi-line textual description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- No custom configuration fields are defined in `LeadQualificationWorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.sales-development-representative.workflows.LeadQualificationWorkflow import (
    LeadQualificationWorkflow,
)

async def main():
    wf = LeadQualificationWorkflow()
    result = await wf.execute({
        "lead_data": {"name": "Acme Corp", "email": "contact@acme.com"},
        "qualification_criteria": "BANT",
    })
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not perform qualification/scoring; it only returns a template payload and planned steps.
- Input keys documented in `execute()` docstring are **not validated or required**; the workflow simply returns the keys received.
