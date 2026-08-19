# ThreatAnalysisWorkflow

## What it is
- A **non-functional (template-only)** workflow for threat assessment and analysis in the *osint-researcher* domain.
- Provides a placeholder `execute()` implementation that returns a template response and logs warnings.

## Public API
- **`ThreatAnalysisWorkflowConfiguration`** (`WorkflowConfiguration`)
  - Configuration dataclass for the workflow (currently no additional fields).
- **`ThreatAnalysisWorkflow`** (`Workflow`)
  - **`__init__(config: Optional[ThreatAnalysisWorkflowConfiguration] = None)`**
    - Initializes the workflow and logs a warning that it is not functional yet.
  - **`async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`**
    - Template execution method; logs a warning and returns a dictionary describing planned steps and received input keys.
  - **`get_workflow_description() -> str`**
    - Returns a human-readable description of the workflow.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` base classes.
- `ThreatAnalysisWorkflowConfiguration` currently has **no custom settings**.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.osint_researcher.workflows.ThreatAnalysisWorkflow import (
    ThreatAnalysisWorkflow,
)

async def main():
    wf = ThreatAnalysisWorkflow()
    result = await wf.execute(
        {
            "domain_specific_input": {"query": "example"},
            "context": "additional context",
            "parameters": {"level": "basic"},
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- Marked **"NOT FUNCTIONAL YET - Template only"**.
- `execute()` does **not** perform threat analysis; it only returns:
  - `status: "template_only"`
  - a `planned_steps` list
  - `inputs_received` (keys of the provided `inputs`)
