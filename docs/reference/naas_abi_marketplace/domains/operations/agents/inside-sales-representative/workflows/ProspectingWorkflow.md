# ProspectingWorkflow

## What it is
- A **non-functional workflow template** for remote prospecting and lead generation.
- Logs warnings indicating it is not implemented yet and returns a placeholder result.

## Public API
- `ProspectingWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow.
  - Currently contains **no additional fields**.

- `ProspectingWorkflow(Workflow)`
  - `__init__(config: Optional[ProspectingWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided configuration or a default `ProspectingWorkflowConfiguration`.
    - Emits a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Placeholder execution method.
    - Emits a warning and returns a dict:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns: `"Remote prospecting and lead generation workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.inside-sales representative.workflows.ProspectingWorkflow import (
    ProspectingWorkflow,
)

async def main():
    wf = ProspectingWorkflow()
    result = await wf.execute({"company": "ACME", "region": "EMEA"})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**:
  - `execute()` is not implemented beyond returning a placeholder response.
  - Instantiation and execution will emit warning logs.
