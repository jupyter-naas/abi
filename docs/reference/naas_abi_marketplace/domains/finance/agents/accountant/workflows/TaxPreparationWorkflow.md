# TaxPreparationWorkflow

## What it is
- A **non-functional (template-only)** workflow class intended for **tax return preparation and filing** in the accountant domain.
- Logs warnings on initialization and execution to indicate it is not implemented yet.
- Returns a placeholder result describing planned steps and received input keys.

## Public API
- `TaxPreparationWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently empty; placeholder).
- `TaxPreparationWorkflow(Workflow)`
  - `__init__(config: Optional[TaxPreparationWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default configuration.
    - Emits a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; emits a warning and returns a placeholder response:
      - `status`: `"template_only"`
      - `message`: not functional yet
      - `planned_steps`: list of intended workflow steps
      - `inputs_received`: list of top-level keys present in `inputs`
  - `get_workflow_description() -> str`
    - Returns a multiline description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` (used for warnings)
- `TaxPreparationWorkflowConfiguration` currently defines no additional fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.accountant.workflows.TaxPreparationWorkflow import (
    TaxPreparationWorkflow,
)

async def main():
    wf = TaxPreparationWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"year": 2025},
            "context": {"jurisdiction": "US"},
            "parameters": {"dry_run": True},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: execution is a stub and does not perform real tax preparation/filing.
- `execute()` returns a placeholder payload and only reflects the **input keys**, not validated/processed content.
