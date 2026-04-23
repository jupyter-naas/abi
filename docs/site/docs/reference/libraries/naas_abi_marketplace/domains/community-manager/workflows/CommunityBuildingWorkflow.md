# CommunityBuildingWorkflow

## What it is
- A **non-functional template** workflow for community building and growth strategy.
- Provides a placeholder implementation that logs warnings and returns a structured “template only” response.

## Public API
- `CommunityBuildingWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty; inherits base configuration behavior).
- `CommunityBuildingWorkflow(Workflow)`
  - `__init__(config: Optional[CommunityBuildingWorkflowConfiguration] = None)`
    - Initializes the workflow with provided config or a default configuration.
    - Emits a warning that it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; emits a warning and returns:
      - `status`: `"template_only"`
      - `message`: `"�� Workflow not functional yet"`
      - `planned_steps`: list of intended steps
      - `inputs_received`: list of keys from the `inputs` dict
  - `get_workflow_description() -> str`
    - Returns a multi-line description of the workflow’s intent.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`.
- Configuration:
  - `CommunityBuildingWorkflowConfiguration` currently defines no additional fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.community-manager.workflows.CommunityBuildingWorkflow import (
    CommunityBuildingWorkflow,
)

async def main():
    wf = CommunityBuildingWorkflow()
    result = await wf.execute({"context": "Example", "parameters": {"foo": "bar"}})
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does not perform real processing; it only returns planned steps and echoes received input keys.
- The returned `message` string contains replacement characters (`"��"`), likely due to encoding issues in the source.
