# FinancialPlanningWorkflow

## What it is
- A **non-functional (template-only)** workflow intended for strategic financial planning and forecasting in the financial-controller domain.
- Logs warnings on initialization and execution to indicate it is not implemented.

## Public API
- `FinancialPlanningWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty).
- `FinancialPlanningWorkflow(Workflow)`
  - `__init__(config: Optional[FinancialPlanningWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Returns a dict describing planned steps and echoing received input keys.
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- `FinancialPlanningWorkflowConfiguration` currently defines no additional fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.financial-controller.workflows.FinancialPlanningWorkflow import (
    FinancialPlanningWorkflow,
)

async def main():
    wf = FinancialPlanningWorkflow()
    result = await wf.execute({"context": "FY forecast", "parameters": {"horizon": 12}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform financial planning; it only returns a template response (`status: "template_only"`).
