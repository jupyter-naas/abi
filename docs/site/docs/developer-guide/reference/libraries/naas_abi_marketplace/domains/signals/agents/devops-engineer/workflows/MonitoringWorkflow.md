# MonitoringWorkflow

## What it is
- A **non-functional workflow template** for system monitoring and alerting setup.
- Provides placeholder behavior: logs warnings and returns a structured “template only” response.

## Public API
- `MonitoringWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty).

- `MonitoringWorkflow(Workflow)`
  - `__init__(config: Optional[MonitoringWorkflowConfiguration] = None)`
    - Initializes the workflow; logs a warning that it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Returns a template response including planned steps and the received input keys.
  - `get_workflow_description() -> str`
    - Returns a human-readable description string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`.
- `MonitoringWorkflowConfiguration` currently has no custom fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.devops_engineer.workflows.MonitoringWorkflow import (
    MonitoringWorkflow,
)

async def main():
    wf = MonitoringWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"target": "host-1"},
            "context": {"env": "prod"},
            "parameters": {"level": "basic"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` is not implemented beyond returning a template payload.
- Always logs warnings on initialization and execution.
