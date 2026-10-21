# CaseDocumentationWorkflow

## What it is
A **non-functional workflow template** for case documentation and reporting in the private investigator domain. It logs warnings on initialization and execution, and returns a placeholder response describing planned steps.

## Public API
- `@dataclass CaseDocumentationWorkflowConfiguration(WorkflowConfiguration)`
  - Purpose: Configuration container for `CaseDocumentationWorkflow` (currently empty).

- `class CaseDocumentationWorkflow(Workflow)`
  - `__init__(config: Optional[CaseDocumentationWorkflowConfiguration] = None)`
    - Purpose: Initialize the workflow with a configuration (or default). Logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Purpose: Template execution entrypoint. Logs a warning and returns a dict indicating `"template_only"`, planned steps, and which input keys were received.
  - `get_workflow_description() -> str`
    - Purpose: Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` (used to emit warnings)
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
- Configuration:
  - `CaseDocumentationWorkflowConfiguration` inherits `WorkflowConfiguration` but defines no additional fields.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.private_investigator.workflows.CaseDocumentationWorkflow import (
    CaseDocumentationWorkflow,
)

async def main():
    wf = CaseDocumentationWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"case_id": "123"},
            "context": {"priority": "high"},
            "parameters": {"format": "pdf"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` is not implemented beyond returning a placeholder response and planned steps.
- Always emits warnings via `logger` during initialization and execution.
