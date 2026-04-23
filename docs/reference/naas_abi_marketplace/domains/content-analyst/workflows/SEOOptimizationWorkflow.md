# SEOOptimizationWorkflow

## What it is
- A **non-functional template** workflow for content SEO analysis and optimization.
- Provides a placeholder `execute()` implementation that logs warnings and returns a stub response.

## Public API
- `SEOOptimizationWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow.
  - Currently has **no custom fields** (`pass`).

- `SEOOptimizationWorkflow(Workflow)`
  - `__init__(config: Optional[SEOOptimizationWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default configuration.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Placeholder execution method.
    - Logs a warning and returns:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Content SEO analysis and optimization workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `SEOOptimizationWorkflowConfiguration` exists but defines **no parameters**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content_analyst.workflows.SEOOptimizationWorkflow import (
    SEOOptimizationWorkflow,
)

async def main():
    wf = SEOOptimizationWorkflow()
    result = await wf.execute({"content": "Hello world", "keywords": ["example"]})
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform SEO analysis; it only returns a stub payload and logs warnings.
