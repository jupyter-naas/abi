# ContentStrategyWorkflow

## What it is
- A **non-functional workflow template** for a comprehensive content strategy development process.
- Provides a placeholder `execute()` implementation that returns planned steps and echoes received input keys.

## Public API
- `@dataclass ContentStrategyWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow.
  - Currently has **no additional fields** beyond `WorkflowConfiguration`.

- `class ContentStrategyWorkflow(Workflow)`
  - `__init__(config: Optional[ContentStrategyWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default `ContentStrategyWorkflowConfiguration`.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; logs a warning and returns a dict with:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `planned_steps`: list of planned step descriptions
      - `inputs_received`: list of input dict keys
    - Docstring lists expected inputs (not enforced):
      - `domain_specific_input`, `context`, `parameters`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Async execution: `execute()` is `async` and must be awaited.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content_strategist.workflows.ContentStrategyWorkflow import (
    ContentStrategyWorkflow,
)

async def main():
    wf = ContentStrategyWorkflow()
    result = await wf.execute({"context": {"brand": "ExampleCo"}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- Marked as **NOT FUNCTIONAL YET**; `execute()` does not implement real workflow logic.
- No validation is performed on inputs; output is a template response.
