# DigitalForensicsWorkflow

## What it is
- A **non-functional (template-only)** workflow class intended for digital forensics investigations in the *osint-researcher* domain.
- Emits warnings on initialization and execution to indicate it is not implemented.

## Public API
- `DigitalForensicsWorkflowConfiguration(WorkflowConfiguration)`
  - Placeholder configuration dataclass (no additional fields).
- `DigitalForensicsWorkflow(Workflow)`
  - `__init__(config: Optional[DigitalForensicsWorkflowConfiguration] = None)`
    - Initializes the workflow with a default configuration if none is provided.
    - Logs a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Logs a warning that it is not implemented.
    - Returns a dict containing:
      - `status`: `"template_only"`
      - `message`: not functional message
      - `planned_steps`: list of planned (string) steps
      - `inputs_received`: list of input keys received
  - `get_workflow_description() -> str`
    - Returns a human-readable description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`
- Configuration:
  - `DigitalForensicsWorkflowConfiguration` currently has **no custom settings**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.osint-researcher.workflows.DigitalForensicsWorkflow import (
    DigitalForensicsWorkflow,
)

async def main():
    wf = DigitalForensicsWorkflow()
    result = await wf.execute({"context": {"case_id": "123"}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` does not perform any real workflow logic and always returns a template response.
- Intended as a scaffold; integration behavior depends on the `Workflow` base class from `naas_abi_core`.
