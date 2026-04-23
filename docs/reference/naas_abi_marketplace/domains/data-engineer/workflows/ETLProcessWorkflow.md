# ETLProcessWorkflow

## What it is
- A **non-functional (template-only)** workflow skeleton for an ETL (Extract, Transform, Load) process optimization workflow.
- Provides placeholder behavior and structured output indicating it is not implemented.

## Public API
- `ETLProcessWorkflowConfiguration(WorkflowConfiguration)`
  - Dataclass configuration container for the workflow (currently empty; inherits base configuration).

- `ETLProcessWorkflow(Workflow)`
  - `__init__(config: Optional[ETLProcessWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that it is not implemented.
    - Returns a dictionary with:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of input keys received
  - `get_workflow_description() -> str`
    - Returns a multi-line description string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base classes
- Configuration:
  - `ETLProcessWorkflowConfiguration` currently has **no fields** (inherits defaults from `WorkflowConfiguration`).

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.data-engineer.workflows.ETLProcessWorkflow import (
    ETLProcessWorkflow,
)

async def main():
    wf = ETLProcessWorkflow()
    result = await wf.execute({"domain_specific_input": "example", "context": {}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform ETL; it only returns template metadata and logs warnings.
