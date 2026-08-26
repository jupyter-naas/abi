# RelationshipManagementWorkflow

## What it is
- A **non-functional workflow template** for stakeholder relationship management in the business development representative domain.
- Implements a skeleton `Workflow` with placeholder execution steps and warning logs.

## Public API

### Classes
- `RelationshipManagementWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty).

- `RelationshipManagementWorkflow(Workflow)`
  - Workflow template with stubbed behavior.

### Methods (RelationshipManagementWorkflow)
- `__init__(config: Optional[RelationshipManagementWorkflowConfiguration] = None)`
  - Initializes the workflow and logs a warning that it is not functional yet.
- `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
  - Template execution that:
    - logs a warning that execution is not implemented,
    - returns a dict with `status`, `message`, `planned_steps`, and `inputs_received`.
- `get_workflow_description() -> str`
  - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs.
  - `naas_abi_core.workflow.workflow.Workflow` base class.
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration` base configuration.
- `RelationshipManagementWorkflowConfiguration` currently defines no fields.

## Usage

```python
import asyncio
from naas_abi_marketplace.domains.business-development-representative.workflows.RelationshipManagementWorkflow import (
    RelationshipManagementWorkflow,
)

async def main():
    wf = RelationshipManagementWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": "example",
            "context": {"audience": "stakeholders"},
            "parameters": {"mode": "template"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- Marked **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does not perform real processing; it returns placeholder metadata and logs warnings.
- The returned `message` contains a likely encoding issue (`"�� Workflow not functional yet"`).
