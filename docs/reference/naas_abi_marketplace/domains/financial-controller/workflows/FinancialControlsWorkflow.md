# FinancialControlsWorkflow

## What it is
- A **non-functional template** workflow for financial controls and compliance tasks in the financial-controller domain.
- Provides a placeholder `execute()` that returns a template response and logs warnings.

## Public API
- `@dataclass FinancialControlsWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty; inherits base configuration).
- `class FinancialControlsWorkflow(Workflow)`
  - `__init__(config: Optional[FinancialControlsWorkflowConfiguration] = None)`
    - Initializes the workflow with provided config (or default) and logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template implementation that logs a warning and returns:
      - `status: "template_only"`
      - `message`
      - `planned_steps` (list of placeholder steps)
      - `inputs_received` (keys of the provided `inputs`)
  - `get_workflow_description() -> str`
    - Returns a multi-line description string of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` (used to emit warnings)
- Configuration:
  - `FinancialControlsWorkflowConfiguration` currently has **no additional fields** beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio

from naas_abi_marketplace.domains.financial-controller.workflows.FinancialControlsWorkflow import (
    FinancialControlsWorkflow,
)

async def main():
    wf = FinancialControlsWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"example": True},
            "context": {"note": "demo"},
            "parameters": {"mode": "test"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform domain logic; it only returns a placeholder structure and logs warnings.
