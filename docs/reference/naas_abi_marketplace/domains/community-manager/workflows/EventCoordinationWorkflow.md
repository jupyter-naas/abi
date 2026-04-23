# EventCoordinationWorkflow

## What it is
- A **non-functional (template-only)** workflow intended for community event planning and coordination.
- Provides a placeholder structure: configuration class, workflow class, and stubbed `execute()` logic.

## Public API
- `EventCoordinationWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty).
- `EventCoordinationWorkflow(Workflow)`
  - `__init__(config: Optional[EventCoordinationWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template implementation that returns:
      - `status`: `"template_only"`
      - `message`: `"�� Workflow not functional yet"`
      - `planned_steps`: list of planned template steps
      - `inputs_received`: list of input keys received
    - Logs a warning that it is not implemented.
  - `get_workflow_description() -> str`
    - Returns a multi-line textual description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `EventCoordinationWorkflowConfiguration` exists but currently defines no fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.community_manager.workflows.EventCoordinationWorkflow import (
    EventCoordinationWorkflow,
)

async def main():
    wf = EventCoordinationWorkflow()
    result = await wf.execute({"context": {"event_type": "meetup"}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- Marked **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does not perform real workflow actions; it returns a template response and logs warnings.
- The returned `message` contains replacement characters (`"��"`), as present in the source.
