# RecruitmentWorkflow

## What it is
- A **non-functional workflow template** intended to represent an end-to-end recruitment and hiring process.
- Provides placeholder behavior: logs warnings and returns a template response describing planned steps.

## Public API

### `RecruitmentWorkflowConfiguration`
- Dataclass extending `WorkflowConfiguration`.
- Purpose: configuration container for `RecruitmentWorkflow` (currently has no additional fields).

### `RecruitmentWorkflow`
Subclass of `naas_abi_core.workflow.workflow.Workflow`.

- `__init__(config: Optional[RecruitmentWorkflowConfiguration] = None)`
  - Initializes the workflow with the provided config or a default `RecruitmentWorkflowConfiguration`.
  - Logs a warning that the workflow is not functional yet.

- `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
  - Template execution method.
  - Returns a dict with:
    - `status`: `"template_only"`
    - `message`: not functional notice
    - `planned_steps`: list of placeholder steps
    - `inputs_received`: list of input keys received
  - Logs a warning that execution is not implemented.

- `get_workflow_description() -> str`
  - Returns a multi-line string describing the intended workflow purpose.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `RecruitmentWorkflowConfiguration` currently adds no fields beyond `WorkflowConfiguration`.

## Usage

```python
import asyncio
from naas_abi_marketplace.domains.human-resources-manager.workflows.RecruitmentWorkflow import (
    RecruitmentWorkflow,
)

async def main():
    wf = RecruitmentWorkflow()
    result = await wf.execute({"domain_specific_input": "example", "context": {}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**:
  - `execute()` does not implement real recruitment logic.
  - Outputs are placeholders intended for scaffolding and integration testing only.
