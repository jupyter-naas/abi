# FinancialReportingWorkflow

## What it is
- A **non-functional workflow template** for financial statement preparation and analysis in the accountant domain.
- Emits warnings on initialization and execution indicating it is **not implemented yet**.
- Returns a stub response describing planned steps and echoing received input keys.

## Public API
- `@dataclass FinancialReportingWorkflowConfiguration(WorkflowConfiguration)`
  - Placeholder configuration class (no additional fields).
- `class FinancialReportingWorkflow(Workflow)`
  - `__init__(config: Optional[FinancialReportingWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning and returns a template result:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `planned_steps`: list of planned step descriptions
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a multiline description of the workflow’s intent.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base types.
- `FinancialReportingWorkflowConfiguration` currently has no custom configuration fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.accountant.workflows.FinancialReportingWorkflow import (
    FinancialReportingWorkflow,
)

async def main():
    wf = FinancialReportingWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"some": "data"},
            "context": {"period": "FY2025"},
            "parameters": {"format": "IFRS"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: execution is a stub and does not perform real financial reporting logic.
- `execute` is **async** and must be awaited.
- Inputs are not validated; only their **keys** are echoed in the response.
