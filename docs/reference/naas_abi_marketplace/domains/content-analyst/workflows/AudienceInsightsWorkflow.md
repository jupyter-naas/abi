# AudienceInsightsWorkflow

## What it is
- A **non-functional workflow template** for audience behavior and preference analysis.
- Provides a placeholder `execute()` implementation that logs warnings and returns a stub response.

## Public API
- `AudienceInsightsWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently contains no fields).
- `AudienceInsightsWorkflow(Workflow)`
  - `__init__(config: Optional[AudienceInsightsWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default configuration.
    - Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that execution is not implemented.
    - Returns a template response including:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns a human-readable description string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`.
- Configuration:
  - `AudienceInsightsWorkflowConfiguration` currently defines **no configurable parameters**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content_analyst.workflows.AudienceInsightsWorkflow import (
    AudienceInsightsWorkflow,
)

async def main():
    wf = AudienceInsightsWorkflow()
    result = await wf.execute({"audience_id": "123", "segment": "prospects"})
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: this is a template-only workflow.
- `execute()` does not perform analysis; it only returns a stub payload and logs warnings.
