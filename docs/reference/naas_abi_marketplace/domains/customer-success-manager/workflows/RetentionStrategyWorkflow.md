# RetentionStrategyWorkflow

## What it is
- A **non-functional workflow template** for customer retention and engagement in the Customer Success Manager domain.
- Provides a placeholder `execute()` implementation that returns a template response and logs warnings.

## Public API
- `@dataclass RetentionStrategyWorkflowConfiguration(WorkflowConfiguration)`
  - Purpose: Configuration container for `RetentionStrategyWorkflow`.
  - Notes: Currently empty (`pass`).

- `class RetentionStrategyWorkflow(Workflow)`
  - `__init__(config: Optional[RetentionStrategyWorkflowConfiguration] = None)`
    - Purpose: Initialize the workflow with a configuration (or a default one).
    - Behavior: Logs a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Purpose: Template execution method.
    - Behavior:
      - Logs a warning that execution is not implemented.
      - Returns a dict containing:
        - `status`: `"template_only"`
        - `message`: `"🚧 Workflow not functional yet"`
        - `planned_steps`: list of planned template steps (strings)
        - `inputs_received`: list of keys from `inputs`
    - Documented expected inputs (not enforced by code):
      - `domain_specific_input`, `context`, `parameters`
  - `get_workflow_description() -> str`
    - Purpose: Returns a multi-line description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `RetentionStrategyWorkflowConfiguration` exists but defines no fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.customer_success_manager.workflows.RetentionStrategyWorkflow import (
    RetentionStrategyWorkflow,
)

async def main():
    wf = RetentionStrategyWorkflow()
    result = await wf.execute({"context": {"account_id": "123"}})
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not implement real retention logic; it only returns template metadata and planned steps.
- Warnings are emitted on initialization and execution via `logger.warning(...)`.
