# EvidenceAnalysisWorkflow

## What it is
- A **non-functional (template-only)** workflow for evidence collection and analysis in the private investigator domain.
- Provides a placeholder `execute()` implementation that returns planned steps and echoes received input keys.

## Public API
- `@dataclass EvidenceAnalysisWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently has no additional fields).
- `class EvidenceAnalysisWorkflow(Workflow)`
  - `__init__(config: Optional[EvidenceAnalysisWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; logs a warning and returns:
      - `status`: `"template_only"`
      - `message`: not functional yet
      - `planned_steps`: list of placeholder steps
      - `inputs_received`: list of input dict keys
  - `get_workflow_description() -> str`
    - Returns a multi-line description string for the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base types.
- `EvidenceAnalysisWorkflowConfiguration` exists but does not define additional options.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.private-investigator.workflows.EvidenceAnalysisWorkflow import (
    EvidenceAnalysisWorkflow,
)

async def main():
    wf = EvidenceAnalysisWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"case_id": "123"},
            "context": "High-level context",
            "parameters": {"mode": "draft"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **“NOT FUNCTIONAL YET - Template only”**.
- `execute()` does not perform real analysis; it returns placeholder metadata and planned steps.
