# CodeReviewWorkflow

## What it is
- A **non-functional workflow template** intended for comprehensive code review (quality, security, performance, best practices).
- Emits warnings on initialization and execution to indicate it is not implemented.

## Public API
- `@dataclass CodeReviewWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration container for the workflow (currently no additional fields).
- `class CodeReviewWorkflow(Workflow)`
  - `__init__(config: Optional[CodeReviewWorkflowConfiguration] = None)`
    - Initializes the workflow and logs a warning that it is template-only.
  - `async execute(inputs: Dict[str, Any]) -> Dict[str, Any]`
    - Template execution method; returns a placeholder response including planned steps and received input keys.
    - Expected input keys (documented): `code`, `language`, `context`.
  - `get_workflow_description() -> str`
    - Returns a multi-line description of intended analysis areas.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger` for warnings.
  - `naas_abi_core.workflow.workflow.Workflow` and `WorkflowConfiguration` as base classes.
- `CodeReviewWorkflowConfiguration` currently has no custom parameters.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.software-engineer.workflows.CodeReviewWorkflow import (
    CodeReviewWorkflow,
)

async def main():
    wf = CodeReviewWorkflow()
    result = await wf.execute(
        {
            "code": "print('hello')",
            "language": "python",
            "context": "demo snippet",
        }
    )
    print(result)

asyncio.run(main())
```

## Caveats
- **Not functional yet**: `execute()` is not implemented and only returns a template payload with `"status": "template_only"`.
- No actual code parsing, analysis, or report generation occurs.
