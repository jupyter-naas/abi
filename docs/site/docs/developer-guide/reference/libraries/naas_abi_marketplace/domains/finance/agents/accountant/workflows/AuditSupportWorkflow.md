# AuditSupportWorkflow

## What it is
- A **non-functional workflow template** for internal audit support and documentation in the accountant domain.
- Emits warnings indicating it is **not implemented yet** and returns a placeholder response.

## Public API

### `AuditSupportWorkflowConfiguration`
- `class AuditSupportWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for `AuditSupportWorkflow`.
  - Currently has **no additional fields** beyond `WorkflowConfiguration`.

### `AuditSupportWorkflow`
- `class AuditSupportWorkflow(Workflow)`
  - Template workflow implementation.

Methods:
- `__init__(config: Optional[AuditSupportWorkflowConfiguration] = None)`
  - Initializes the workflow with the provided config or a default `AuditSupportWorkflowConfiguration`.
  - Logs a warning that the workflow is template-only.

- `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
  - Placeholder execution method.
  - Logs a warning that it is not implemented.
  - Returns a dict containing:
    - `status`: `"template_only"`
    - `message`: not-functional notice
    - `planned_steps`: list of planned template steps
    - `inputs_received`: list of input keys received

- `get_workflow_description() -> str`
  - Returns a multiline description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` (logs warnings)
- Configuration:
  - `AuditSupportWorkflowConfiguration` exists but **does not define extra parameters**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.accountant.workflows.AuditSupportWorkflow import (
    AuditSupportWorkflow,
)

async def main():
    wf = AuditSupportWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"example": True},
            "context": "Audit support context",
            "parameters": {"strict": False},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` is a template and does not perform real audit support logic.
- Always returns `status="template_only"` and logs warnings during initialization and execution.
