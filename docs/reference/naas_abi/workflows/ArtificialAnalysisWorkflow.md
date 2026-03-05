# ArtificialAnalysisWorkflow

## What it is
- A workflow that fetches model data from the Artificial Analysis API, optionally filters the results to only providers that have corresponding local agent modules, and saves the result as a timestamped JSON file under a fixed storage path.

## Public API
- **`ArtificialAnalysisWorkflowConfiguration`** (`WorkflowConfiguration`, `dataclass`)
  - `api_key: str`: Artificial Analysis API key (required).
  - `base_url: str = "https://artificialanalysis.ai/api/v2"`: API base URL.
- **`ArtificialAnalysisWorkflowParameters`** (`WorkflowParameters`)
  - `endpoint: str = "llms"`: Endpoint to fetch (e.g., `"llms"` or media endpoints like `"text-to-image"`).
  - `include_categories: bool = False`: Adds `include_categories=true` query param for media endpoints.
  - `validate_agents_only: bool = True`: If `True`, filters models to those with corresponding local agent modules.
- **`ArtificialAnalysisWorkflow`** (`Workflow`)
  - `__init__(configuration: ArtificialAnalysisWorkflowConfiguration)`: Stores configuration.
  - `run_workflow(parameters: ArtificialAnalysisWorkflowParameters) -> dict`: Fetches API data, optionally filters, writes JSON to disk, returns summary dict.
  - `as_tools() -> list[BaseTool]`: Exposes a LangChain `StructuredTool` named `artificial_analysis_data_fetch`.
  - `as_api(...) -> None`: Present but intentionally does nothing (returns `None`).

> Internal helpers (not public API): `_fetch_models_data`, `_get_modules_with_agents`, `_filter_data_for_valid_modules`, `_extract_module_name_from_model`.

## Configuration/Dependencies
- **Network/API**
  - Uses `requests.get` with header `x-api-key: <api_key>`.
  - URL logic:
    - If `endpoint == "llms"`: `.../data/llms/models`
    - Else: `.../data/media/{endpoint}`
- **Filesystem**
  - Scans for modules with agents under: `src/core/modules/<module>/agents/*Agent.py`
  - Saves output JSON under:
    - `storage/datastore/core/modules/abi/ArtificialAnalysisWorkflow/<timestamp>_<endpoint>_data.json`
- **Key libraries**
  - `requests`, `pydantic`, `langchain_core.tools`, `naas_abi_core.workflow`

## Usage
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

print(result["status"], result["output_file"])
```

## Caveats
- Filtering via `validate_agents_only=True` depends on the local repository layout existing at `src/core/modules` and containing `agents/*Agent.py` files; if the path is missing, no modules are considered valid.
- `as_api(...)` is a no-op and does not register any routes.
- Provider-to-module matching uses a fixed mapping (e.g., `"openai" -> "chatgpt"`, `"anthropic" -> "claude"`) and fallbacks based on provider/model name heuristics; mismatches may cause models to be filtered out.
