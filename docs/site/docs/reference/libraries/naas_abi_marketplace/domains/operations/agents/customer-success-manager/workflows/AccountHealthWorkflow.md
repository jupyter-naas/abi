# AccountHealthWorkflow

## What it is
- A **non-functional template** workflow for **account health monitoring and intervention** in the customer success manager domain.
- Provides placeholders for future workflow logic and returns a structured template response.
- Logs warnings on initialization and execution to indicate it is not implemented.

## Public API
- `@dataclass AccountHealthWorkflowConfiguration(WorkflowConfiguration)`
  - Purpose: Configuration container for `AccountHealthWorkflow`.
  - Notes: Currently empty (`pass`).

- `class AccountHealthWorkflow(Workflow)`
  - `__init__(config: Optional[AccountHealthWorkflowConfiguration] = None)`
    - Purpose: Initialize the workflow; uses a default `AccountHealthWorkflowConfiguration` if none provided.
    - Side effects: Logs a warning that the workflow is not functional.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Purpose: Template execution method; returns a dictionary describing planned steps and received input keys.
    - Side effects: Logs a warning that execution is not implemented.
    - Expected `inputs` keys (documented): `domain_specific_input`, `context`, `parameters`.
  - `get_workflow_description() -> str`
    - Purpose: Returns a human-readable description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` base classes.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.customer_success_manager.workflows.AccountHealthWorkflow import (
    AccountHealthWorkflow,
)

async def main():
    wf = AccountHealthWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"account_id": "A-123"},
            "context": {"region": "EMEA"},
            "parameters": {"verbose": True},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not implement account health logic; it returns a template payload with:
  - `status: "template_only"`
  - `message`
  - `planned_steps`
  - `inputs_received` (list of input keys)
