# AudienceAnalysisWorkflow

## What it is
- A **non-functional workflow template** for target audience research and analysis in the "content-strategist" domain.
- Provides a placeholder `execute()` implementation that returns planned steps and echoes received input keys.

## Public API
- `AudienceAnalysisWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow (currently empty; inherits base configuration behavior).
- `AudienceAnalysisWorkflow(Workflow)`
  - `__init__(config: Optional[AudienceAnalysisWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; logs a warning and returns a dict with:
      - `status`: `"template_only"`
      - `message`: not functional notice
      - `planned_steps`: list of planned step strings
      - `inputs_received`: list of keys from `inputs`
  - `get_workflow_description() -> str`
    - Returns a multi-line description string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings
  - `naas_abi_core.workflow.workflow.Workflow` base class
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration` base configuration class
- `AudienceAnalysisWorkflowConfiguration` currently defines **no additional fields**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content_strategist.workflows.AudienceAnalysisWorkflow import (
    AudienceAnalysisWorkflow,
)

async def main():
    wf = AudienceAnalysisWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"topic": "B2B SaaS"},
            "context": {"goal": "increase signups"},
            "parameters": {"depth": "high"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- Marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does not perform real analysis; it only returns a placeholder response and logs warnings.
