# DataPipelineWorkflow

## What it is
- A **non-functional workflow template** for data pipeline design and implementation in the data engineer domain.
- Provides placeholder behavior and returns a structured “template_only” response.

## Public API
- `@dataclass DataPipelineWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for `DataPipelineWorkflow` (currently empty).
- `class DataPipelineWorkflow(Workflow)`
  - `__init__(config: Optional[DataPipelineWorkflowConfiguration] = None)`
    - Initializes the workflow; logs a warning that it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; logs a warning and returns:
      - `status`: `"template_only"`
      - `message`: non-functional notice
      - `planned_steps`: list of intended workflow steps (strings)
      - `inputs_received`: list of received input keys
  - `get_workflow_description() -> str`
    - Returns a multi-line description of the workflow’s intended purpose.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger`
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- `DataPipelineWorkflowConfiguration` currently adds no fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.data_engineer.workflows.DataPipelineWorkflow import (
    DataPipelineWorkflow,
)

async def main():
    wf = DataPipelineWorkflow()
    result = await wf.execute({
        "domain_specific_input": {"source": "db", "target": "warehouse"},
        "context": {"sla": "daily"},
        "parameters": {"mode": "incremental"},
    })
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform real processing; it only returns a template response and logs warnings.
