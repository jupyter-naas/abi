# ContentAnalysisWorkflow

## What it is
- A **non-functional workflow template** for “Comprehensive content performance analysis”.
- Provides a placeholder `execute()` implementation that only logs warnings and returns a stub response.

## Public API
- `ContentAnalysisWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow.
  - Currently has **no additional fields** (inherits everything from `WorkflowConfiguration`).

- `ContentAnalysisWorkflow(Workflow)`
  - `__init__(config: Optional[ContentAnalysisWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default `ContentAnalysisWorkflowConfiguration`.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that it is not implemented.
    - Returns a stub dictionary:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys received
  - `get_workflow_description() -> str`
    - Returns: `"Comprehensive content performance analysis workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` (used for warnings)

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content-analyst.workflows.ContentAnalysisWorkflow import (
    ContentAnalysisWorkflow,
)

async def main():
    wf = ContentAnalysisWorkflow()
    result = await wf.execute({"content_id": "123", "metrics": ["views", "clicks"]})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does not perform analysis; it only returns a stub response and logs warnings.
