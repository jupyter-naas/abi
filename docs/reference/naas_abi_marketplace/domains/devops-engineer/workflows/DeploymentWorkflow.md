# DeploymentWorkflow

## What it is
- A **non-functional template** workflow intended for application deployment and rollback tasks.
- Implements a placeholder `execute()` that returns a template response and logs warnings.

## Public API
- `DeploymentWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty; inherits base configuration behavior).
- `DeploymentWorkflow(Workflow)`
  - `__init__(config: Optional[DeploymentWorkflowConfiguration] = None)`
    - Initializes the workflow with a provided configuration or a default one.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Placeholder execution method.
    - Returns a dict containing:
      - `status`: `"template_only"`
      - `message`: non-functional notice
      - `planned_steps`: list of intended steps (strings)
      - `inputs_received`: list of input keys received
  - `get_workflow_description() -> str`
    - Returns a multi-line string describing the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow` base class
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration` base configuration
- Configuration:
  - `DeploymentWorkflowConfiguration` currently defines no additional fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.devops_engineer.workflows.DeploymentWorkflow import (
    DeploymentWorkflow,
)

async def main():
    wf = DeploymentWorkflow()
    result = await wf.execute({"context": {"env": "staging"}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform deployment/rollback; it only returns a template payload and logs warnings.
