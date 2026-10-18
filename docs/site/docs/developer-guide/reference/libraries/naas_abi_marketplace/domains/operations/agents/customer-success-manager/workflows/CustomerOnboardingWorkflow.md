# CustomerOnboardingWorkflow

## What it is
- A **non-functional workflow template** for a “New customer onboarding and setup” process in the customer-success-manager domain.
- Provides placeholder behavior: logs warnings and returns a static “template_only” result describing planned steps.

## Public API
- `CustomerOnboardingWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty; inherits defaults from `WorkflowConfiguration`).

- `CustomerOnboardingWorkflow(Workflow)`
  - `__init__(config: Optional[CustomerOnboardingWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default configuration.
    - Emits a warning indicating the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Emits a warning indicating it is not implemented.
    - Returns:
      - `status`: `"template_only"`
      - `message`: static message
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.customer_success_manager.workflows.CustomerOnboardingWorkflow import (
    CustomerOnboardingWorkflow,
)

async def main():
    wf = CustomerOnboardingWorkflow()
    result = await wf.execute({"context": {"customer_id": "123"}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- Marked **NOT FUNCTIONAL YET**; `execute()` does not perform real onboarding logic.
- Always returns a template response with `status="template_only"` and logs warnings on initialization and execution.
