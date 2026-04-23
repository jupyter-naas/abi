# ClientRetentionWorkflow

## What it is
- A **non-functional workflow template** intended for client retention and satisfaction optimization.
- Emits warnings on initialization and execution to indicate it is not implemented.

## Public API
- `ClientRetentionWorkflowConfiguration(WorkflowConfiguration)`
  - Workflow configuration dataclass (currently has no custom fields).
- `ClientRetentionWorkflow(Workflow)`
  - `__init__(config: Optional[ClientRetentionWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning and returns a placeholder response:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Client retention and satisfaction optimization workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` base class.
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration` base configuration.
- `ClientRetentionWorkflowConfiguration` currently does not define additional configuration fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.account_executive.workflows.ClientRetentionWorkflow import (
    ClientRetentionWorkflow,
)

async def main():
    wf = ClientRetentionWorkflow()
    result = await wf.execute({"client_id": "123", "notes": "check-in"})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform any real processing; it only returns a placeholder payload and logs warnings.
