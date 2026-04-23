# SuccessMetricsWorkflow

## What it is
- A **non-functional workflow template** for customer success metrics tracking and reporting.
- Logs warnings on initialization and execution.
- Returns a stubbed response describing planned steps and echoing received input keys.

## Public API
- `SuccessMetricsWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty / no custom fields).

- `SuccessMetricsWorkflow(Workflow)`
  - `__init__(config: Optional[SuccessMetricsWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default config.
    - Emits a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; emits a warning and returns:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a descriptive multi-line string about the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `SuccessMetricsWorkflowConfiguration` currently has **no additional options** beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.customer_success_manager.workflows.SuccessMetricsWorkflow import (
    SuccessMetricsWorkflow,
)

async def main():
    wf = SuccessMetricsWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"customer_id": "C123"},
            "context": {"reporting_period": "Q1"},
            "parameters": {"format": "summary"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` is not implemented and always returns a template response with status `"template_only"`.
