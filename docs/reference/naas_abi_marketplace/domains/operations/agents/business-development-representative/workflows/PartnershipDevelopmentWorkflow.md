# PartnershipDevelopmentWorkflow

## What it is
A **non-functional workflow template** for strategic partnership development and management in the business development representative domain. It currently logs warnings and returns placeholder output.

## Public API
- `@dataclass PartnershipDevelopmentWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow.
  - Currently has no additional fields beyond `WorkflowConfiguration`.

- `class PartnershipDevelopmentWorkflow(Workflow)`
  - `__init__(config: Optional[PartnershipDevelopmentWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided configuration (or a default one).
    - Emits a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Placeholder execution method.
    - Logs a warning and returns a template response including planned steps and received input keys.
  - `get_workflow_description() -> str`
    - Returns a human-readable description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger`
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `PartnershipDevelopmentWorkflowConfiguration` (empty extension of `WorkflowConfiguration`).

## Usage
```python
import asyncio

from naas_abi_marketplace.domains.business-development-representative.workflows.PartnershipDevelopmentWorkflow import (
    PartnershipDevelopmentWorkflow,
)

async def main():
    wf = PartnershipDevelopmentWorkflow()
    result = await wf.execute({"domain_specific_input": "example", "context": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` is not implemented and returns a placeholder dict with:
  - `status: "template_only"`
  - `planned_steps` (static list)
  - `inputs_received` (keys from `inputs`)
