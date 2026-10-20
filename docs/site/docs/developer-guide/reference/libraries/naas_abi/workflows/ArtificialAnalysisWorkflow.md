# ArtificialAnalysisWorkflow

## What it is
A `Workflow` that:
- Fetches model data from the Artificial Analysis API (LLMs or media endpoints).
- Optionally filters the results to only include providers that have corresponding local agent modules.
- Persists the (optionally filtered) response as a timestamped JSON file under `storage/datastore/core/modules/abi/ArtificialAnalysisWorkflow`.

## Public API
### Classes
- `ArtificialAnalysisWorkflowConfiguration(WorkflowConfiguration)`
  - Holds API connection settings.
  - Fields:
    - `api_key: str` (required)
    - `base_url: str` (default: `https://artificialanalysis.ai/api/v2`)

- `ArtificialAnalysisWorkflowParameters(WorkflowParameters)`
  - Input parameters for execution.
  - Fields:
    - `endpoint: str` (default: `"llms"`) — endpoint to fetch (e.g., `"llms"`, `"text-to-image"`, etc.)
    - `include_categories: bool` (default: `False`) — adds `include_categories=true` query param for media endpoints
    - `validate_agents_only: bool` (default: `True`) — if `True`, filters models to only those with local agent modules

- `ArtificialAnalysisWorkflow(Workflow)`
  - Main workflow implementation.

### Methods
- `ArtificialAnalysisWorkflow.run_workflow(parameters: ArtificialAnalysisWorkflowParameters) -> dict`
  - Executes fetch → optional filter → save JSON.
  - Returns a dict including:
    - `status` (`"success"` or `"error"`)
    - `endpoint`, `models_count`, `original_count`, `valid_modules`, `output_file`, `timestamp` (on success)

- `ArtificialAnalysisWorkflow.as_tools() -> list[BaseTool]`
  - Exposes the workflow as a LangChain `StructuredTool` named `artificial_analysis_data_fetch`.
  - Tool calls into `self.run(ArtificialAnalysisWorkflowParameters(**kwargs))`.

- `ArtificialAnalysisWorkflow.as_api(...) -> None`
  - Present but not implemented (returns `None`).

## Configuration/Dependencies
- Network:
  - Uses `requests.get` with header `x-api-key: <api_key>`.
- Filesystem:
  - Writes JSON files to: `storage/datastore/core/modules/abi/ArtificialAnalysisWorkflow/`.
  - When `validate_agents_only=True`, scans local modules under: `src/core/modules/*/agents/*Agent.py`.
- Key dependencies:
  - `requests`
  - `pydantic` (for `Field` / schema)
  - `langchain_core.tools` (for `StructuredTool`)
  - `naas_abi_core.workflow` base classes

## Usage
Minimal direct invocation:

```python
from naas_abi.workflows.ArtificialAnalysisWorkflow import (
    ArtificialAnalysisWorkflow,
    ArtificialAnalysisWorkflowConfiguration,
    ArtificialAnalysisWorkflowParameters,
)

wf = ArtificialAnalysisWorkflow(
    ArtificialAnalysisWorkflowConfiguration(api_key="YOUR_ARTIFICIAL_ANALYSIS_API_KEY")
)

result = wf.run_workflow(
    ArtificialAnalysisWorkflowParameters(
        endpoint="llms",
        include_categories=False,
        validate_agents_only=True,
    )
)

print(result["status"], result.get("output_file"))
```

Using as a LangChain tool:

```python
wf = ArtificialAnalysisWorkflow(
    ArtificialAnalysisWorkflowConfiguration(api_key="YOUR_ARTIFICIAL_ANALYSIS_API_KEY")
)

tool = wf.as_tools()[0]
out = tool.invoke({"endpoint": "llms", "validate_agents_only": False})
print(out)
```

## Caveats
- `validate_agents_only=True` depends on the local repository layout:
  - If `src/core/modules` does not exist, filtering will effectively keep all models (no valid modules found).
- `as_api(...)` is a stub and does not register any routes.
- The workflow prints progress and filtering details to stdout.
