# InvestmentStrategyWorkflow

## What it is
- A **non-functional template** workflow for investment planning and portfolio management.
- Logs warnings on initialization and execution to indicate it is not implemented.

## Public API
- `InvestmentStrategyWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow.
  - Currently contains **no additional fields** (inherits base `WorkflowConfiguration`).

- `InvestmentStrategyWorkflow(Workflow)`
  - `__init__(config: Optional[InvestmentStrategyWorkflowConfiguration] = None)`
    - Initializes the workflow with provided config or a default configuration.
    - Emits a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Emits a warning that execution is not implemented.
    - Returns a fixed response:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Investment planning and portfolio management workflow"`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warning logs)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.treasurer.workflows.InvestmentStrategyWorkflow import (
    InvestmentStrategyWorkflow,
)

async def main():
    wf = InvestmentStrategyWorkflow()
    result = await wf.execute({"budget": 1000, "risk_profile": "balanced"})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform any investment logic; it only returns a placeholder payload and logs warnings.
