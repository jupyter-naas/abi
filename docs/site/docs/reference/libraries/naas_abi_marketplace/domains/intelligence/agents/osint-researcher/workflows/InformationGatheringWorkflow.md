# InformationGatheringWorkflow

## What it is
- A **non-functional template** workflow for open source intelligence (OSINT) information gathering.
- Provides a placeholder `execute()` implementation that returns planned steps and echoes received input keys.
- Emits warnings on initialization and execution to indicate it is not implemented.

## Public API
- `InformationGatheringWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty).

- `InformationGatheringWorkflow(Workflow)`
  - `__init__(config: Optional[InformationGatheringWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default configuration.
    - Logs a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; logs a warning and returns:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of placeholder workflow steps
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- Configuration:
  - `InformationGatheringWorkflowConfiguration` currently has no custom fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.osint_researcher.workflows.InformationGatheringWorkflow import (
    InformationGatheringWorkflow,
)

async def main():
    wf = InformationGatheringWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": "target name",
            "context": {"goal": "basic OSINT overview"},
            "parameters": {"depth": "light"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **NOT FUNCTIONAL YET**:
  - `execute()` does not perform OSINT gathering; it only returns a template response.
  - Warnings are logged on initialization and execution.
