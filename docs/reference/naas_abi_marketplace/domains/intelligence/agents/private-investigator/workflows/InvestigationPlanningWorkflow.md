# InvestigationPlanningWorkflow

## What it is
- A **non-functional workflow template** for “investigation planning and case setup” in the private investigator domain.
- Implements a placeholder `execute()` that returns a static template response and logs warnings.

## Public API
- `@dataclass InvestigationPlanningWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty; inherits base configuration behavior).
- `class InvestigationPlanningWorkflow(Workflow)`
  - `__init__(config: Optional[InvestigationPlanningWorkflowConfiguration] = None)`
    - Initializes the workflow with provided config or a default configuration.
    - Logs a warning that it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Placeholder execution method.
    - Returns:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of template step descriptions
      - `inputs_received`: list of keys from the `inputs` dict
  - `get_workflow_description() -> str`
    - Returns a multi-line textual description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `InvestigationPlanningWorkflowConfiguration` exists but does not define additional fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.private-investigator.workflows.InvestigationPlanningWorkflow import (
    InvestigationPlanningWorkflow,
)

async def main():
    wf = InvestigationPlanningWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"case_type": "background_check"},
            "context": {"priority": "high"},
            "parameters": {"format": "summary"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform real processing; it only returns a template payload and logs warnings.
