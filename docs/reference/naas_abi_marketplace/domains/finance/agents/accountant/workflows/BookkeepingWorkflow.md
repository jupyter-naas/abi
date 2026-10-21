# BookkeepingWorkflow

## What it is
- A **non-functional workflow template** for “Comprehensive bookkeeping and transaction processing” in the accountant domain.
- Provides a stubbed `execute()` that returns a template response and logs warnings.

## Public API
- `@dataclass BookkeepingWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for `BookkeepingWorkflow` (currently empty; inherits base workflow configuration).
- `class BookkeepingWorkflow(Workflow)`
  - `__init__(config: Optional[BookkeepingWorkflowConfiguration] = None)`
    - Initializes the workflow with a provided config or a default configuration.
    - Emits a warning that the workflow is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; logs a warning and returns a dict describing planned steps and received input keys.
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base classes.
- `BookkeepingWorkflowConfiguration` currently defines no additional fields beyond `WorkflowConfiguration`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.accountant.workflows.BookkeepingWorkflow import (
    BookkeepingWorkflow,
)

async def main():
    wf = BookkeepingWorkflow()
    result = await wf.execute({
        "domain_specific_input": {},
        "context": {"company": "ExampleCo"},
        "parameters": {"dry_run": True},
    })
    print(result)

asyncio.run(main())
```

## Caveats
- Marked as **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does **not** perform bookkeeping; it returns a template payload with:
  - `status: "template_only"`
  - `planned_steps`
  - `inputs_received` (list of input dict keys)
