# CICDPipelineWorkflow

## What it is
- A **non-functional template** workflow class for a Continuous Integration / Continuous Deployment (CI/CD) pipeline.
- Intended for the **devops-engineer** domain, but currently only logs warnings and returns a placeholder response.

## Public API
- `@dataclass CICDPipelineWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration holder for the workflow.
  - Currently **empty** (no additional fields).

- `class CICDPipelineWorkflow(Workflow)`
  - `__init__(config: Optional[CICDPipelineWorkflowConfiguration] = None)`
    - Initializes the workflow with the provided config or a default `CICDPipelineWorkflowConfiguration`.
    - Logs a warning indicating it is not functional yet.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Placeholder execution method.
    - Logs a warning that it is not implemented.
    - Returns a dict containing:
      - `status`: `"template_only"`
      - `message`: `"🚧 Workflow not functional yet"`
      - `planned_steps`: list of planned step descriptions (strings)
      - `inputs_received`: list of input keys received
  - `get_workflow_description() -> str`
    - Returns a multi-line string describing the workflow at a high level.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warning logs.
  - `naas_abi_core.workflow.workflow.Workflow` base class.
  - `naas_abi_core.workflow.workflow.WorkflowConfiguration` base configuration class.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.devops_engineer.workflows.CICDPipelineWorkflow import (
    CICDPipelineWorkflow,
)

async def main():
    wf = CICDPipelineWorkflow()
    result = await wf.execute({"domain_specific_input": "value", "context": {}, "parameters": {}})
    print(result)

asyncio.run(main())
```

## Caveats
- This workflow is explicitly marked **NOT FUNCTIONAL YET**.
- `execute()` does not perform any CI/CD actions; it only returns a template response and logs warnings.
