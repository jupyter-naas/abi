# PerformanceOptimizationWorkflow

## What it is
- A **non-functional (template-only)** workflow class intended for application performance analysis and optimization.
- Provides a placeholder `execute()` implementation that returns metadata about planned steps and received inputs.

## Public API
- `@dataclass PerformanceOptimizationWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration holder for the workflow (currently has no additional fields).

- `class PerformanceOptimizationWorkflow(Workflow)`
  - `__init__(config: Optional[PerformanceOptimizationWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that it is not implemented and returns:
      - `status`: `"template_only"`
      - `message`: indicates not functional
      - `planned_steps`: list of placeholder step descriptions
      - `inputs_received`: list of keys found in `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base classes.
- `PerformanceOptimizationWorkflowConfiguration` currently does not define any configuration fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.software-engineer.workflows.PerformanceOptimizationWorkflow import (
    PerformanceOptimizationWorkflow,
)

async def main():
    wf = PerformanceOptimizationWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"app": "example"},
            "context": "some context",
            "parameters": {"level": "basic"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not perform real analysis/optimization; it only returns a template response and logs warnings.
