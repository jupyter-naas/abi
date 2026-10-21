# AccountManagementWorkflow

## What it is
- A **non-functional workflow template** intended for comprehensive account management and relationship building.
- Currently logs warnings on initialization and execution and returns a placeholder response.

## Public API
- `AccountManagementWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently has no additional fields).
- `AccountManagementWorkflow(Workflow)`
  - `__init__(config: Optional[AccountManagementWorkflowConfiguration] = None)`
    - Initializes the workflow with a configuration (defaults to an empty `AccountManagementWorkflowConfiguration`) and logs a warning that it is not functional.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that execution is not implemented and returns a placeholder dict:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns a static description string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow` base class
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration` base configuration class
- `AccountManagementWorkflowConfiguration` currently defines no additional configuration options.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.account-executive.workflows.AccountManagementWorkflow import (
    AccountManagementWorkflow,
)

async def main():
    wf = AccountManagementWorkflow()
    result = await wf.execute({"account_id": "123", "action": "sync"})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform any real processing; it only returns a placeholder response and logs warnings.
