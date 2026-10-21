# RiskMitigationWorkflow

## What it is
- A **non-functional template** workflow for project risk identification and mitigation.
- Provides a placeholder `execute()` implementation that returns planned steps and echoes received input keys.
- Emits warnings via `naas_abi_core.logger` indicating it is not implemented.

## Public API
- `@dataclass RiskMitigationWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently no additional fields).
- `class RiskMitigationWorkflow(Workflow)`
  - `__init__(config: Optional[RiskMitigationWorkflowConfiguration] = None)`
    - Initializes the workflow with a provided config or a default configuration.
    - Logs a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Logs a warning that execution is not implemented.
    - Returns a dict with:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- Configuration:
  - `RiskMitigationWorkflowConfiguration` extends `WorkflowConfiguration` but adds no fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.project-manager.workflows.RiskMitigationWorkflow import (
    RiskMitigationWorkflow,
)

async def main():
    wf = RiskMitigationWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"project_id": "P-123"},
            "context": {"timeline": "Q3"},
            "parameters": {"mode": "dry_run"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does not perform risk analysis/mitigation; it only returns placeholder metadata and planned steps.
