# ArchitectureDesignWorkflow

## What it is
- A **non-functional workflow template** for software architecture design and documentation.
- Provides a placeholder `execute()` implementation that returns planned steps and echoes received input keys.
- Emits warnings via `naas_abi_core.logger` indicating it is not implemented.

## Public API
- `ArchitectureDesignWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty; inherits base configuration).
- `ArchitectureDesignWorkflow(Workflow)`
  - `__init__(config: Optional[ArchitectureDesignWorkflowConfiguration] = None)`
    - Initializes the workflow with provided config or a default configuration.
    - Logs a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; logs a warning that it is not implemented.
    - Returns a dict with:
      - `status`: `"template_only"`
      - `message`: indicates not functional
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base classes
- Configuration:
  - `ArchitectureDesignWorkflowConfiguration` exists but contains no additional fields.

## Usage
```python
import asyncio

from naas_abi_marketplace.domains.software-engineer.workflows.ArchitectureDesignWorkflow import (
    ArchitectureDesignWorkflow,
)

async def main():
    wf = ArchitectureDesignWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": "High-level requirements",
            "context": {"system": "example"},
            "parameters": {"detail_level": "low"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not perform architecture design; it returns template metadata only.
- The returned payload is informational (planned steps, input keys) and should not be treated as a completed workflow result.
