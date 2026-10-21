# CashManagementWorkflow

## What it is
- A **non-functional workflow template** intended for cash flow management and optimization.
- Logs warnings indicating it is not implemented yet.
- Returns a placeholder response from `execute()`.

## Public API
- `@dataclass CashManagementWorkflowConfiguration(WorkflowConfiguration)`
  - Workflow configuration container (currently empty).

- `class CashManagementWorkflow(Workflow)`
  - `__init__(config: Optional[CashManagementWorkflowConfiguration] = None)`
    - Initializes the workflow with provided config or a default configuration.
    - Emits a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Placeholder implementation.
    - Emits a warning that execution is not implemented.
    - Returns a dict containing:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns: `"Cash flow management and optimization workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- Configuration:
  - `CashManagementWorkflowConfiguration` currently defines no additional fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.treasurer.workflows.CashManagementWorkflow import (
    CashManagementWorkflow,
)

async def main():
    wf = CashManagementWorkflow()
    result = await wf.execute({"cash_in": 1000, "cash_out": 500})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform any cash management logic; it only returns a template response and logs warnings.
