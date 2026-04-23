# SocialMediaWorkflow

## What it is
- A **non-functional workflow template** for social media content creation and scheduling.
- Provides placeholder behavior: logs warnings and returns a template response describing planned steps.

## Public API
- `@dataclass SocialMediaWorkflowConfiguration(WorkflowConfiguration)`
  - Workflow configuration container (currently empty).

- `class SocialMediaWorkflow(Workflow)`
  - `__init__(config: Optional[SocialMediaWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config (or a default config).
    - Emits a warning indicating the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Returns a dict with:
      - `status`: `"template_only"`
      - `message`: not functional indicator
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of input keys received
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- `SocialMediaWorkflowConfiguration` currently defines no additional fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio

from naas_abi_marketplace.domains.content-creator.workflows.SocialMediaWorkflow import (
    SocialMediaWorkflow,
)

async def main():
    wf = SocialMediaWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"topic": "launch post"},
            "context": {"audience": "developers"},
            "parameters": {"platform": "linkedin"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- Marked in code as **NOT FUNCTIONAL YET** (template only).
- `execute()` does not implement real workflow logic; it only returns planned steps and echoes input keys.
