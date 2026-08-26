# PerformanceOptimizationWorkflow

## What it is
- A **non-functional workflow template** intended for campaign performance analysis and optimization.
- Logs warnings on initialization and execution to indicate it is not implemented.

## Public API
- `PerformanceOptimizationWorkflowConfiguration(WorkflowConfiguration)`
  - Placeholder configuration dataclass (no additional fields).

- `PerformanceOptimizationWorkflow(Workflow)`
  - `__init__(config: Optional[PerformanceOptimizationWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided configuration or a default configuration.
    - Emits a warning that this is a template only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Returns a dict with:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
    - Emits a warning that execution is not implemented.
  - `get_workflow_description() -> str`
    - Returns: `"Campaign performance analysis and optimization workflow"`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used to emit warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`

## Usage
```python
import asyncio

from naas_abi_marketplace.domains.campaign-manager.workflows.PerformanceOptimizationWorkflow import (
    PerformanceOptimizationWorkflow,
)

async def main():
    wf = PerformanceOptimizationWorkflow()
    result = await wf.execute({"campaign_id": "123", "window": "7d"})
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform any optimization; it only returns a placeholder response and logs a warning.
