# SocialMediaManagementWorkflow

## What it is
- A **non-functional workflow template** for multi-platform social media management in the community-manager domain.
- Logs warnings on initialization and execution to indicate it is **not implemented yet**.

## Public API

### `SocialMediaManagementWorkflowConfiguration`
- `class SocialMediaManagementWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for `SocialMediaManagementWorkflow`.
  - Currently has **no additional fields** beyond `WorkflowConfiguration`.

### `SocialMediaManagementWorkflow`
- `class SocialMediaManagementWorkflow(Workflow)`
  - Template workflow implementation.

#### `__init__(config: Optional[SocialMediaManagementWorkflowConfiguration] = None)`
- Initializes the workflow with the provided configuration, or a default `SocialMediaManagementWorkflowConfiguration`.
- Emits a warning via `naas_abi_core.logger` that the workflow is template-only.

#### `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
- Template async executor; **does not perform real work**.
- Emits a warning that `execute()` is not implemented.
- Returns a dict containing:
  - `status`: `"template_only"`
  - `message`: `"�� Workflow not functional yet"` (note: contains replacement characters as written)
  - `planned_steps`: a list of placeholder steps
  - `inputs_received`: list of keys provided in `inputs`

Expected `inputs` (documented in docstring):
- `domain_specific_input`
- `context`
- `parameters`

#### `get_workflow_description() -> str`
- Returns a multi-line string describing the intended purpose of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `SocialMediaManagementWorkflowConfiguration` subclasses `WorkflowConfiguration` but defines no custom parameters.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.community_manager.workflows.SocialMediaManagementWorkflow import (
    SocialMediaManagementWorkflow,
)

async def main():
    wf = SocialMediaManagementWorkflow()
    result = await wf.execute(
        {"domain_specific_input": {}, "context": {}, "parameters": {}}
    )
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**:
  - `execute()` only returns placeholder content and does not implement social media management logic.
- The returned `message` contains `"��"` exactly as in source, indicating an encoding/replacement-character issue in the template text.
