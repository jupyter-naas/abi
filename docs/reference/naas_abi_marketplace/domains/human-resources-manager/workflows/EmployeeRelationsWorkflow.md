# EmployeeRelationsWorkflow

## What it is
- A **non-functional workflow template** for employee relations and conflict resolution in the human resources manager domain.
- Logs warnings on initialization and execution to indicate it is **not implemented yet**.

## Public API
- `EmployeeRelationsWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty; inherits base configuration behavior).

- `EmployeeRelationsWorkflow(Workflow)`
  - `__init__(config: Optional[EmployeeRelationsWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default configuration.
    - Emits a warning: workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Returns a dict indicating `"template_only"`, planned steps, and the list of input keys received.
  - `get_workflow_description() -> str`
    - Returns a human-readable description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` (used to log warnings)
- Configuration:
  - `EmployeeRelationsWorkflowConfiguration` currently defines no additional fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.human-resources-manager.workflows.EmployeeRelationsWorkflow import (
    EmployeeRelationsWorkflow,
)

async def main():
    wf = EmployeeRelationsWorkflow()
    result = await wf.execute({
        "domain_specific_input": "Example issue",
        "context": {"employee_id": "E123"},
        "parameters": {"priority": "high"},
    })
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform real processing; it only returns a template response and logs a warning.
