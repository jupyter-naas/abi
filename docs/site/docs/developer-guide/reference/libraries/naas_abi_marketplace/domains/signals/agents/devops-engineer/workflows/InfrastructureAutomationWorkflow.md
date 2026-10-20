# InfrastructureAutomationWorkflow

## What it is
- A **non-functional workflow template** intended for infrastructure-as-code automation in the DevOps Engineer domain.
- Provides a placeholder configuration class and a stub `execute()` implementation that returns template metadata.

## Public API
- `InfrastructureAutomationWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow.
  - Currently has **no additional fields** beyond `WorkflowConfiguration`.

- `InfrastructureAutomationWorkflow(Workflow)`
  - `__init__(config: Optional[InfrastructureAutomationWorkflowConfiguration] = None)`
    - Initializes the workflow with a provided config or a default `InfrastructureAutomationWorkflowConfiguration`.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Stubbed execution method.
    - Logs a warning that execution is not implemented.
    - Returns a dict with:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of planned template steps
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- Configuration:
  - `InfrastructureAutomationWorkflowConfiguration` currently adds **no extra configuration**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.devops_engineer.workflows.InfrastructureAutomationWorkflow import (
    InfrastructureAutomationWorkflow,
)

async def main():
    wf = InfrastructureAutomationWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"example": True},
            "context": {"env": "dev"},
            "parameters": {"dry_run": True},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform real automation; it only returns a template response and planned steps.
