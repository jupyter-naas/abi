# RiskAssessmentWorkflow

## What it is
- A **non-functional workflow template** for “Financial risk analysis and mitigation”.
- Emits warnings on initialization and execution to indicate it is not implemented.

## Public API
- `@dataclass RiskAssessmentWorkflowConfiguration(WorkflowConfiguration)`
  - Placeholder configuration class (currently has no additional fields).
- `class RiskAssessmentWorkflow(Workflow)`
  - `__init__(config: Optional[RiskAssessmentWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning and returns a template response:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns `"Financial risk analysis and mitigation workflow"`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` (used for warnings)

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.treasurer.workflows.RiskAssessmentWorkflow import (
    RiskAssessmentWorkflow,
)

async def main():
    wf = RiskAssessmentWorkflow()
    result = await wf.execute({"portfolio_id": "P-123", "date": "2026-01-01"})
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: no real risk assessment logic is implemented.
- `execute()` only returns a template payload and logs warnings.
