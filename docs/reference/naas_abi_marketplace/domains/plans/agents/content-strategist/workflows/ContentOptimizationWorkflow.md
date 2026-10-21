# ContentOptimizationWorkflow

## What it is
- A **non-functional (template-only)** workflow scaffold for “content performance optimization” in the content-strategist domain.
- Provides a configuration class and a workflow class that logs warnings and returns a template response from `execute()`.

## Public API

### `ContentOptimizationWorkflowConfiguration`
- **Type:** `@dataclass` extending `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- **Purpose:** Placeholder configuration for the workflow (no additional fields defined).

### `ContentOptimizationWorkflow`
- **Base class:** `naas_abi_core.workflow.workflow.Workflow`

#### `__init__(config: Optional[ContentOptimizationWorkflowConfiguration] = None)`
- Initializes the workflow using the provided config or a default `ContentOptimizationWorkflowConfiguration()`.
- Logs a warning indicating the workflow is not functional yet.

#### `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
- Template async execution method.
- Logs a warning that execution is not implemented.
- Returns a dict containing:
  - `status`: `"template_only"`
  - `message`: not functional notice
  - `planned_steps`: list of planned (placeholder) steps
  - `inputs_received`: list of input keys received

#### `get_workflow_description() -> str`
- Returns a multi-line textual description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- Configuration:
  - `ContentOptimizationWorkflowConfiguration` currently has **no custom fields**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content_strategist.workflows.ContentOptimizationWorkflow import (
    ContentOptimizationWorkflow,
)

async def main():
    wf = ContentOptimizationWorkflow()
    result = await wf.execute({"context": "optimize SEO", "parameters": {"lang": "en"}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform optimization; it only returns a template response and logs warnings.
