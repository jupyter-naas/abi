# LeadConversionWorkflow

## What it is
- A **non-functional (template-only)** workflow class for inbound lead qualification and conversion.
- Logs warnings on initialization and execution to indicate it is not implemented.

## Public API
- `LeadConversionWorkflowConfiguration(WorkflowConfiguration)`
  - Placeholder configuration dataclass for the workflow (no additional fields defined).
- `LeadConversionWorkflow(Workflow)`
  - `__init__(config: Optional[LeadConversionWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default `LeadConversionWorkflowConfiguration`.
    - Emits a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method.
    - Emits a warning and returns a static response including:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Inbound lead qualification and conversion workflow"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.workflow.workflow.Workflow`
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration`
  - `naas_abi_core.logger` (used for warnings)

## Usage
```python
import asyncio

from naas_abi_marketplace.domains.inside_sales_representative.workflows.LeadConversionWorkflow import (
    LeadConversionWorkflow,
)

async def main():
    wf = LeadConversionWorkflow()
    result = await wf.execute({"lead_id": "123", "source": "webform"})
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` is not implemented beyond returning a template response.
- Expect warning logs during initialization and execution.
