# CreatePresentationFromTemplateWorkflow

## What it is
A workflow that builds a new `.pptx` from an existing PowerPoint template and a list of slide instructions. It:
- duplicates specified template slides into a new presentation,
- updates shapes’ text,
- writes slide sources into notes,
- saves the result to object storage,
- uploads the `.pptx` as a public Naas asset,
- registers the template and generated presentation in a triple store via a pipeline.

## Public API
- **`CreatePresentationFromTemplateWorkflowConfiguration`** (`WorkflowConfiguration`, `@dataclass`)
  - Holds dependencies and runtime settings:
    - `triple_store: ITripleStoreService`
    - `powerpoint_configuration: PowerPointIntegrationConfiguration`
    - `naas_configuration: NaasIntegrationConfiguration`
    - `pipeline_configuration: AddPowerPointPresentationPipelineConfiguration`
    - `datastore_path: str = "datastore/powerpoint/presentations"`
    - `workspace_id: str` (default from `ABIModule.get_instance().configuration.workspace_id`)
    - `storage_name: str` (default from `ABIModule.get_instance().configuration.storage_name`)

- **`CreatePresentationFromTemplateWorkflowParameters`** (`WorkflowParameters`)
  - Inputs:
    - `presentation_name: str` (if missing `.pptx`, it is appended)
    - `slides_data: list[dict]` (per-slide instructions; see below)
    - `template_path: str` (path to `.pptx` template file)

- **`CreatePresentationFromTemplateWorkflow`** (`Workflow`)
  - **`create_presentation(parameters) -> dict[str, Any]`**
    - Generates the presentation, saves it, uploads it to Naas, and registers both template and output via `AddPowerPointPresentationPipeline`.
    - Returns:
      - `presentation_name`: ensured to end with `.pptx`
      - `storage_path`: `<datastore_path>/<presentation_name>`
      - `download_url`: returned from Naas upload (`asset["asset_url"]`)
      - `presentation_uri`: URI from pipeline graph (first `OWL.NamedIndividual`), or `None`
      - `template_uri`: URI from template pipeline graph, or `None`
  - **`as_tools() -> list[BaseTool]`**
    - Exposes a LangChain `StructuredTool` named `create_presentation_from_template` that calls `self.run(...)` with `CreatePresentationFromTemplateWorkflowParameters`.
  - **`as_api(...) -> None`**
    - Present but does not register any routes (method body ends without implementation).

### `slides_data` expected keys
Each item is a `dict` where the workflow reads:
- `template_slide_number` *(required)*: index of the slide in the template to duplicate
- `shapes` *(optional, default `[]`)*: list of dicts with:
  - `shape_id`
  - `text`
- `sources` *(optional, default `[]`)*: list of strings to write into slide notes

## Configuration/Dependencies
- **PowerPoint**
  - Uses `PowerPointIntegration` constructed with `powerpoint_configuration` for:
    - `create_presentation(template_path)`
    - `remove_all_slides(presentation)`
    - `duplicate_slide(template_presentation, template_slide_number, presentation)`
    - `update_shape(presentation, slide_idx, shape_id, text)`
    - `update_notes(presentation, slide_idx, sources)`
- **Naas**
  - Uses `NaasIntegration` constructed with `naas_configuration`:
    - `upload_asset(... visibility="public", return_url=True)` to obtain `asset_url`
- **Storage**
  - Uses `StorageUtils(ABIModule.get_instance().engine.services.object_storage)`
  - Persists via `save_powerpoint_presentation(..., copy=False)` into `datastore_path`
- **Triple store / pipeline**
  - Runs `AddPowerPointPresentationPipeline` twice:
    - once for the template (`presentation_name=os.path.basename(template_path)`, `storage_path=template_path`)
    - once for the generated presentation (includes `download_url` and `template_uri`)
  - Extracts the first subject with `(RDF.type, OWL.NamedIndividual)` as the URI (or `None`).

## Usage
```python
from naas_abi_marketplace.applications.powerpoint.workflows.CreatePresentationFromTemplateWorkflow import (
    CreatePresentationFromTemplateWorkflow,
    CreatePresentationFromTemplateWorkflowConfiguration,
    CreatePresentationFromTemplateWorkflowParameters,
)

# Provide these from your environment/runtime
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegrationConfiguration,
)
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from naas_abi_marketplace.applications.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    AddPowerPointPresentationPipelineConfiguration,
)

cfg = CreatePresentationFromTemplateWorkflowConfiguration(
    triple_store=triple_store,  # ITripleStoreService
    powerpoint_configuration=PowerPointIntegrationConfiguration(...),
    naas_configuration=NaasIntegrationConfiguration(...),
    pipeline_configuration=AddPowerPointPresentationPipelineConfiguration(...),
)

wf = CreatePresentationFromTemplateWorkflow(cfg)

result = wf.create_presentation(
    CreatePresentationFromTemplateWorkflowParameters(
        presentation_name="deck",
        template_path="templates/base.pptx",
        slides_data=[
            {
                "template_slide_number": 0,
                "shapes": [{"shape_id": "Title 1", "text": "Updated title"}],
                "sources": ["https://example.com"],
            }
        ],
    )
)

print(result["storage_path"])
print(result["download_url"])
```

Using as a LangChain tool:
```python
tool = wf.as_tools()[0]
out = tool.run(
    {
        "presentation_name": "deck",
        "template_path": "templates/base.pptx",
        "slides_data": [],
    }
)
```

## Caveats
- If a `slides_data` item lacks `template_slide_number`, it is skipped (an error is logged).
- Shape updates and notes updates are individually wrapped in `try/except`; failures log errors and the workflow continues.
- `as_api()` does not expose endpoints in its current form.
- `workspace_id` and `storage_name` default from `ABIModule`; the workflow assumes `ABIModule.get_instance()` and its `engine.services.object_storage` are available.
