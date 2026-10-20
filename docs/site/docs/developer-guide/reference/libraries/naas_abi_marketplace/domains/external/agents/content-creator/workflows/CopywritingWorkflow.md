# CopywritingWorkflow

## What it is
- A **non-functional template** workflow for professional copywriting and editing.
- Logs warnings on initialization and execution and returns a placeholder response describing planned steps.

## Public API
- `@dataclass CopywritingWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for `CopywritingWorkflow` (currently no additional fields).

- `class CopywritingWorkflow(Workflow)`
  - `__init__(config: Optional[CopywritingWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided configuration (or defaults).
    - Emits a warning that it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; emits a warning and returns:
      - `status`: `"template_only"`
      - `message`: indicates not functional
      - `planned_steps`: list of planned workflow steps (strings)
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base classes
- Configuration:
  - `CopywritingWorkflowConfiguration` extends `WorkflowConfiguration` but adds no fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content_creator.workflows.CopywritingWorkflow import (
    CopywritingWorkflow,
)

async def main():
    wf = CopywritingWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": "Draft blog intro about X",
            "context": "Target audience: beginners",
            "parameters": {"tone": "professional"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- Marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform copywriting; it only returns placeholder metadata and planned steps.
