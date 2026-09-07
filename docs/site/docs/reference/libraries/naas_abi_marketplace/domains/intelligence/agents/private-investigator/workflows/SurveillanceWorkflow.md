# SurveillanceWorkflow

## What it is
- A **non-functional template** workflow for surveillance planning and coordination in the private investigator domain.
- Provides a configuration class, a workflow skeleton, and placeholder outputs while logging warnings that it is not implemented.

## Public API
- `SurveillanceWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for `SurveillanceWorkflow`.
  - Currently has **no additional fields** beyond the base `WorkflowConfiguration`.

- `SurveillanceWorkflow(Workflow)`
  - `__init__(config: Optional[SurveillanceWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default `SurveillanceWorkflowConfiguration`.
    - Emits a warning via `naas_abi_core.logger` indicating it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Logs a warning that it is not implemented.
    - Returns a dict with:
      - `status`: `"template_only"`
      - `message`: not functional message
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of received input keys
  - `get_workflow_description() -> str`
    - Returns a multi-line textual description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `SurveillanceWorkflowConfiguration` currently adds no extra configuration properties.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.private-investigator.workflows.SurveillanceWorkflow import (
    SurveillanceWorkflow,
)

async def main():
    wf = SurveillanceWorkflow()
    result = await wf.execute({"context": {"case_id": "123"}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform domain logic; it only returns placeholder metadata and planned steps.
