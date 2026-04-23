# CostAnalysisWorkflow

## What it is
- A **non-functional (template-only)** workflow for cost analysis and optimization in the *financial controller* domain.
- Provides a placeholder `execute()` implementation that returns planned steps and echoes received input keys.

## Public API
- `@dataclass CostAnalysisWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty).

- `class CostAnalysisWorkflow(Workflow)`
  - `__init__(config: Optional[CostAnalysisWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config (or a default one).
    - Logs a warning indicating the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Logs a warning that it is not implemented.
    - Returns a dict with:
      - `status: "template_only"`
      - `message`
      - `planned_steps` (static list of steps)
      - `inputs_received` (list of input keys)
  - `get_workflow_description() -> str`
    - Returns a multi-line description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base classes.
- `CostAnalysisWorkflowConfiguration` currently has no additional fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.financial-controller.workflows.CostAnalysisWorkflow import (
    CostAnalysisWorkflow,
)

async def main():
    wf = CostAnalysisWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"example": True},
            "context": {"currency": "USD"},
            "parameters": {"mode": "dry_run"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform cost analysis; it only returns a template response and planned steps.
