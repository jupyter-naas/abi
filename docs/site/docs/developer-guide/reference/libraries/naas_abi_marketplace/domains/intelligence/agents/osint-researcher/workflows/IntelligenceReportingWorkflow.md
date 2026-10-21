# IntelligenceReportingWorkflow

## What it is
- A **non-functional workflow template** for “Intelligence report creation and dissemination” in the OSINT researcher domain.
- Logs warnings indicating it is **not implemented yet** and returns a placeholder response describing planned steps.

## Public API
- `@dataclass IntelligenceReportingWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow.
  - Currently has **no additional fields**.

- `class IntelligenceReportingWorkflow(Workflow)`
  - `__init__(config: Optional[IntelligenceReportingWorkflowConfiguration] = None)`
    - Initializes the workflow using the provided config or a default configuration.
    - Emits a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template implementation that:
      - Emits a warning that execution is not implemented.
      - Returns a dict with:
        - `status`: `"template_only"`
        - `message`: `"🚧 Workflow not functional yet"`
        - `planned_steps`: list of placeholder step descriptions
        - `inputs_received`: list of input dict keys
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`.
- Configuration:
  - `IntelligenceReportingWorkflowConfiguration` is required by the base `Workflow` but currently carries no parameters.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.osint-researcher.workflows.IntelligenceReportingWorkflow import (
    IntelligenceReportingWorkflow,
)

async def main():
    wf = IntelligenceReportingWorkflow()
    result = await wf.execute(
        {"domain_specific_input": "example", "context": {}, "parameters": {}}
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not perform real workflow logic; it returns a placeholder payload and logs warnings.
