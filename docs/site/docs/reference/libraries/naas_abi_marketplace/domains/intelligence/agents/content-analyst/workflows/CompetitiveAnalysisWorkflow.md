# CompetitiveAnalysisWorkflow

## What it is
- A **non-functional template** for a content competitive analysis and benchmarking workflow.
- Logs warnings indicating it is not implemented yet and returns a placeholder response from `execute`.

## Public API
- `CompetitiveAnalysisWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration dataclass for the workflow.
  - Currently has **no additional fields** beyond `WorkflowConfiguration`.

- `CompetitiveAnalysisWorkflow(Workflow)`
  - `__init__(config: Optional[CompetitiveAnalysisWorkflowConfiguration] = None)`
    - Initializes the workflow with provided config or a default `CompetitiveAnalysisWorkflowConfiguration`.
    - Emits a warning that the workflow is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template implementation:
      - Emits a warning that `execute()` is not implemented.
      - Returns a dict with:
        - `status`: `"template_only"`
        - `message`: `"🚧 Workflow not functional yet"`
        - `inputs_received`: list of input keys
  - `get_workflow_description() -> str`
    - Returns: `"Content competitive analysis and benchmarking workflow"`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration`.
- Configuration:
  - `CompetitiveAnalysisWorkflowConfiguration` currently does not define custom parameters.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.content-analyst.workflows.CompetitiveAnalysisWorkflow import (
    CompetitiveAnalysisWorkflow,
)

async def main():
    wf = CompetitiveAnalysisWorkflow()
    result = await wf.execute({"query": "example", "limit": 5})
    print(result)

asyncio.run(main())
```

## Caveats
- The workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform analysis; it only returns a placeholder payload and logs warnings.
