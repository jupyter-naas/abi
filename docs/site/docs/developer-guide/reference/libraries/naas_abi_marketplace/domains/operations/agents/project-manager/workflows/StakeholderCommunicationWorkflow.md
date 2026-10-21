# StakeholderCommunicationWorkflow

## What it is
- A **non-functional (template-only)** workflow intended for stakeholder communication and reporting in the project-manager domain.
- Provides a placeholder `execute()` that returns a structured template response and logs warnings indicating it is not implemented.

## Public API
- `@dataclass StakeholderCommunicationWorkflowConfiguration(WorkflowConfiguration)`
  - Purpose: Configuration container for the workflow (currently empty).

- `class StakeholderCommunicationWorkflow(Workflow)`
  - `__init__(config: Optional[StakeholderCommunicationWorkflowConfiguration] = None)`
    - Purpose: Initialize the workflow with a configuration (or default) and log that it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Purpose: Template async execution method; logs a warning and returns:
      - `status: "template_only"`
      - `message`
      - `planned_steps` (list of placeholder steps)
      - `inputs_received` (list of keys from `inputs`)
  - `get_workflow_description() -> str`
    - Purpose: Return a descriptive multi-line string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` (used for warnings)
- Configuration:
  - `StakeholderCommunicationWorkflowConfiguration` exists but has no fields.

## Usage
```python
import asyncio

from naas_abi_marketplace.domains.project-manager.workflows.StakeholderCommunicationWorkflow import (
    StakeholderCommunicationWorkflow,
)

async def main():
    wf = StakeholderCommunicationWorkflow()
    result = await wf.execute({"context": {"project": "Alpha"}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- Marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not implement real stakeholder communication logic; it only returns a template response and warnings are logged.
