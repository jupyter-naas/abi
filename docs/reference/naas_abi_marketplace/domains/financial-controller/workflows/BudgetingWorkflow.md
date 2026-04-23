# BudgetingWorkflow

## What it is
- A **non-functional workflow template** for budget creation and management in the financial-controller domain.
- Provides a placeholder `execute()` implementation that returns a static “template_only” response and logs warnings.

## Public API
- `@dataclass BudgetingWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for `BudgetingWorkflow` (currently empty; inherits base workflow configuration).

- `class BudgetingWorkflow(Workflow)`
  - `__init__(config: Optional[BudgetingWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default `BudgetingWorkflowConfiguration`.
    - Emits a warning that it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution entrypoint.
    - Logs a warning and returns:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of input keys received
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warning logs)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- `BudgetingWorkflowConfiguration` currently defines no additional fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.financial-controller.workflows.BudgetingWorkflow import (
    BudgetingWorkflow,
)

async def main():
    wf = BudgetingWorkflow()
    result = await wf.execute({"context": {"currency": "USD"}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **“NOT FUNCTIONAL YET - template only”**.
- `execute()` does not perform budgeting logic; it only returns placeholder data and echoes input keys.
