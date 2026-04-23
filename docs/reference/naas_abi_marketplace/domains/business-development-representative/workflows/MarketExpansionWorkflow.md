# MarketExpansionWorkflow

## What it is
- A **non-functional template** workflow for “market expansion and penetration strategy”.
- Provides a placeholder `execute()` implementation that returns a structured “template_only” response and logs warnings.

## Public API
- `MarketExpansionWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty).

- `MarketExpansionWorkflow(Workflow)`
  - `__init__(config: Optional[MarketExpansionWorkflowConfiguration] = None)`
    - Initializes the workflow with a default configuration if none is provided.
    - Emits a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Returns:
      - `status`: `"template_only"`
      - `message`: indicates non-functional state
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of input keys received
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- Configuration:
  - `MarketExpansionWorkflowConfiguration` currently defines no fields (inherits from `WorkflowConfiguration`).

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.business-development-representative.workflows.MarketExpansionWorkflow import (
    MarketExpansionWorkflow,
)

async def main():
    wf = MarketExpansionWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"target_market": "EU"},
            "context": {"goal": "expansion"},
            "parameters": {"depth": "high"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **“NOT FUNCTIONAL YET - template only”**.
- `execute()` does not perform real processing; it only returns planned steps and the keys of received inputs.
- Instantiation and execution will emit warning logs via `logger.warning()`.
