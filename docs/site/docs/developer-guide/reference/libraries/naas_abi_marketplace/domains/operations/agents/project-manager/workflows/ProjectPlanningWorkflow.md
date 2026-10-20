# ProjectPlanningWorkflow

## What it is
- A **non-functional template** workflow for comprehensive project planning.
- Provides a placeholder `execute()` that returns template metadata (no real planning logic).

## Public API
- `@dataclass ProjectPlanningWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty).

- `class ProjectPlanningWorkflow(Workflow)`
  - `__init__(config: Optional[ProjectPlanningWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is **template only**.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Logs a warning that it is not implemented.
    - Returns a dict with:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `planned_steps`: list of planned step descriptions
      - `inputs_received`: list of input keys received
    - Documented expected input keys:
      - `project_name`, `objectives`, `scope`, `timeline`, `resources`, `stakeholders`
  - `get_workflow_description() -> str`
    - Returns a multi-line description of intended capabilities.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- `ProjectPlanningWorkflowConfiguration` currently has no additional fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.project-manager.workflows.ProjectPlanningWorkflow import (
    ProjectPlanningWorkflow,
)

async def main():
    wf = ProjectPlanningWorkflow()
    result = await wf.execute(
        {
            "project_name": "Example Project",
            "objectives": ["Deliver MVP"],
            "scope": "Core features",
            "timeline": {"start": "2026-01-01"},
            "resources": {"team": 3},
            "stakeholders": ["PM", "Engineering"],
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not generate real plans; it only returns template steps and echoes received input keys.
- Emits warnings on initialization and execution via `naas_abi_core.logger`.
