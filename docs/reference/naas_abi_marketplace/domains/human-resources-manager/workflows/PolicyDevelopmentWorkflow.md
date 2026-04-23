# PolicyDevelopmentWorkflow

## What it is
- A **non-functional workflow template** for HR policy development and implementation.
- Provides a skeleton `execute()` method that returns a placeholder response and logs warnings.

## Public API
- `PolicyDevelopmentWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently has no custom fields).
- `PolicyDevelopmentWorkflow(Workflow)`
  - `__init__(config: Optional[PolicyDevelopmentWorkflowConfiguration] = None)`
    - Initializes the workflow with a default configuration when none is provided.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; logs a warning and returns a placeholder payload including:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of planned template steps
      - `inputs_received`: list of input keys provided
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base classes
- Configuration:
  - `PolicyDevelopmentWorkflowConfiguration` extends `WorkflowConfiguration` but defines no additional options.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.human-resources-manager.workflows.PolicyDevelopmentWorkflow import (
    PolicyDevelopmentWorkflow,
)

async def main():
    wf = PolicyDevelopmentWorkflow()
    result = await wf.execute({
        "domain_specific_input": "Draft remote work policy",
        "context": {"region": "EU"},
        "parameters": {"priority": "high"},
    })
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**:
  - `execute()` is not implemented beyond returning a template response.
  - Do not rely on it for real policy development automation.
