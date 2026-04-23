# VideoScriptWorkflow

## What it is
- A **non-functional (template-only)** workflow stub for “video script writing and storyboard creation”.
- Provides a placeholder `execute()` implementation that returns a template response and logs warnings.

## Public API
- `VideoScriptWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently no additional fields).
- `VideoScriptWorkflow(Workflow)`
  - `__init__(config: Optional[VideoScriptWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is not functional.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template async executor; returns a dict with:
      - `status`: `"template_only"`
      - `message`: non-functional notice
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of keys provided in `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger`
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- `VideoScriptWorkflowConfiguration` currently adds no configuration fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content_creator.workflows.VideoScriptWorkflow import (
    VideoScriptWorkflow,
)

async def main():
    wf = VideoScriptWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": "topic / brief",
            "context": "target audience, tone",
            "parameters": {"length": "short"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does not perform real processing; it only returns placeholder metadata and logs warnings.
