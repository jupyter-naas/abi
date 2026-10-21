# TreasuryOperationsWorkflow

## What it is
- A **non-functional workflow template** for “Treasury operations and compliance”.
- Provides a placeholder `execute()` that logs warnings and returns a simple status payload.

## Public API
- `@dataclass TreasuryOperationsWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration object for the workflow.
  - Currently has **no additional fields** beyond `WorkflowConfiguration`.

- `class TreasuryOperationsWorkflow(Workflow)`
  - `__init__(config: Optional[TreasuryOperationsWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config, or a default configuration.
    - Emits a warning that this workflow is a template only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that it is not implemented.
    - Returns a dict:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Treasury operations and compliance workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used to log warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `TreasuryOperationsWorkflowConfiguration` is defined but empty (inherits all behavior/fields from `WorkflowConfiguration`).

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.treasurer.workflows.TreasuryOperationsWorkflow import (
    TreasuryOperationsWorkflow,
)

async def main():
    wf = TreasuryOperationsWorkflow()
    result = await wf.execute({"amount": 100, "currency": "USD"})
    print(result)

asyncio.run(main())
```

## Caveats
- Marked **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does not perform treasury operations; it only returns a placeholder response and logs warnings.
