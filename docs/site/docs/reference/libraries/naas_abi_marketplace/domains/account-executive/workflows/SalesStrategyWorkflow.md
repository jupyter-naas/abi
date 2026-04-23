# SalesStrategyWorkflow

## What it is
- A **non-functional workflow template** for strategic sales planning and execution.
- Emits warnings on initialization and execution to indicate it is not implemented.

## Public API
- `SalesStrategyWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow.
  - Currently contains no additional fields beyond `WorkflowConfiguration`.

- `SalesStrategyWorkflow(Workflow)`
  - `__init__(config: Optional[SalesStrategyWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default configuration.
    - Logs a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that execution is not implemented.
    - Returns a template response:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Strategic sales planning and execution workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` for warnings
- Configuration:
  - `SalesStrategyWorkflowConfiguration` is a passthrough configuration (no custom fields).

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.account-executive.workflows.SalesStrategyWorkflow import (
    SalesStrategyWorkflow,
)

async def main():
    wf = SalesStrategyWorkflow()
    result = await wf.execute({"account_id": "123", "region": "EMEA"})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform any sales strategy logic; it only returns a stub payload and logs warnings.
