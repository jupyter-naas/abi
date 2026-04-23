# DataArchitectureWorkflow

## What it is
- A **non-functional (template-only)** workflow scaffold for *data architecture planning and design* in the data-engineer domain.
- Provides a placeholder `execute()` that returns planned steps and echoes received input keys.
- Logs warnings indicating it is not implemented.

## Public API

### `DataArchitectureWorkflowConfiguration`
- `class DataArchitectureWorkflowConfiguration(WorkflowConfiguration)`
  - Purpose: Configuration container for `DataArchitectureWorkflow`.
  - Notes: Currently has no additional fields (inherits base configuration).

### `DataArchitectureWorkflow`
- `class DataArchitectureWorkflow(Workflow)`
  - Purpose: Template workflow implementation.

#### `__init__(config: Optional[DataArchitectureWorkflowConfiguration] = None)`
- Initializes the workflow with the provided configuration or a default `DataArchitectureWorkflowConfiguration`.
- Emits a warning via `naas_abi_core.logger` that it is template-only.

#### `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
- Template execution method (not implemented).
- Expected (documented) input keys:
  - `domain_specific_input`
  - `context`
  - `parameters`
- Returns a dict containing:
  - `status`: `"template_only"`
  - `message`: `"🚧 Workflow not functional yet"`
  - `planned_steps`: list of placeholder steps
  - `inputs_received`: list of keys provided in `inputs`

#### `get_workflow_description() -> str`
- Returns a multiline string describing the workflow’s intent.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (for warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `DataArchitectureWorkflowConfiguration` extends `WorkflowConfiguration` but adds no custom settings.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.data-engineer.workflows.DataArchitectureWorkflow import (
    DataArchitectureWorkflow,
)

async def main():
    wf = DataArchitectureWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"example": True},
            "context": {"project": "demo"},
            "parameters": {"mode": "dry-run"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly **not functional yet**:
  - `execute()` only returns a template response and planned steps.
  - Warnings are logged on initialization and execution.
