# PerformanceOptimizationWorkflow

## What it is
- A **non-functional (template-only)** workflow class intended for **data processing performance optimization** in the data engineer domain.
- Provides a placeholder `execute()` implementation that returns a template response and logs warnings.

## Public API
- `@dataclass PerformanceOptimizationWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty).
- `class PerformanceOptimizationWorkflow(Workflow)`
  - `__init__(config: Optional[PerformanceOptimizationWorkflowConfiguration] = None)`
    - Initializes the workflow with a provided config or a default configuration.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Logs a warning that it is not implemented.
    - Returns a dict containing:
      - `status`: `"template_only"`
      - `message`: not-functional notice
      - `planned_steps`: list of placeholder step descriptions
      - `inputs_received`: list of keys received in `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line textual description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `PerformanceOptimizationWorkflowConfiguration` currently defines **no additional fields** beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.data_engineer.workflows.PerformanceOptimizationWorkflow import (
    PerformanceOptimizationWorkflow,
)

async def main():
    wf = PerformanceOptimizationWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"example": True},
            "context": "optimize a data pipeline",
            "parameters": {"target": "latency"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform any optimization; it only returns a template payload and emits warnings.
