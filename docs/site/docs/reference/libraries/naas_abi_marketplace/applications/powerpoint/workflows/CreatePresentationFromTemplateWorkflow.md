# CreatePresentationFromTemplateWorkflow

## What it is
A workflow that generates a new PowerPoint presentation from a `.pptx` template plus JSON-like slide instructions (duplicate specific template slides, update shapes’ text, and write sources into slide notes). It saves the resulting file to object storage, uploads a public asset to Naas, and registers both the template and generated presentation in a triple store.

## Public API
- **`CreatePresentationFromTemplateWorkflowConfiguration`** (`WorkflowConfiguration`)
  - Holds dependencies and settings:
    - `triple_store: ITripleStoreService`
    - `powerpoint_configuration: PowerPointIntegrationConfiguration`
    - `naas_configuration: NaasIntegrationConfiguration`
    - `pipeline_configuration: AddPowerPointPresentationPipelineConfiguration`
    - `datastore_path: str = "datastore/powerpoint/presentations"`
    - `workspace_id` (defaults from `ABIModule` configuration)
    - `storage_name` (defaults from `ABIModule` configuration)

- **`CreatePresentationFromTemplateWorkflowParameters`** (`WorkflowParameters`)
  - Execution inputs:
    - `presentation_name: str` (without extension; `.pptx` is enforced)
    - `slides_data: List[Dict]` (per-slide instructions)
    - `template_path: str` (path to `.pptx` template)

- **`CreatePresentationFromTemplateWorkflow`** (`Workflow`)
  - `create_presentation(parameters) -> Dict[str, Any]`
    - Creates the presentation, saves it, uploads it publicly, and registers metadata in a triple store.
    - Returns:
      - `presentation_name` (ensured to end with `.pptx`)
      - `storage_path` (datastore path where saved)
      - `download_url` (public asset URL from Naas)
      - `presentation_uri` (triple store URI if available)
      - `template_uri` (template triple store URI if available)
  - `as_tools() -> list[BaseTool]`
    - Exposes the workflow as a LangChain `StructuredTool` named `create_presentation_from_template`.
  - `as_api(...) -> None`
    - Present but not implemented (returns `None` and does not register routes).

## Configuration/Dependencies
- **Integrations used internally**
  - `PowerPointIntegration` (created from `powerpoint_configuration`)
    - Used to load template, remove slides, duplicate slides, update shapes, and update notes.
  - `NaasIntegration` (created from `naas_configuration`)
    - Used to upload the resulting `.pptx` as a public asset and return a URL.
- **Storage**
  - `StorageUtils` initialized from `ABIModule.get_instance().engine.services.object_storage`
  - Saves presentations under `datastore_path`.
- **Triple store**
  - `AddPowerPointPresentationPipeline` is run twice:
    - Once for the template (to get `template_uri`)
    - Once for the generated presentation (includes `download_url` and `template_uri`)

## Usage
Minimal example (requires valid integration configurations and ABIModule engine context):

```python
from naas_abi_marketplace.applications.powerpoint.workflows.CreatePresentationFromTemplateWorkflow import (
    CreatePresentationFromTemplateWorkflow,
    CreatePresentationFromTemplateWorkflowConfiguration,
    CreatePresentationFromTemplateWorkflowParameters,
)

# You must provide real implementations/configs for these:
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import PowerPointIntegrationConfiguration
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import NaasIntegrationConfiguration
from naas_abi_marketplace.applications.powerpoint.pipelines.AddPowerPointPresentationPipeline import AddPowerPointPresentationPipelineConfiguration

# triple_store: ITripleStoreService must be provided by your runtime/container.
cfg = CreatePresentationFromTemplateWorkflowConfiguration(
    triple_store=triple_store,
    powerpoint_configuration=PowerPointIntegrationConfiguration(...),
    naas_configuration=NaasIntegrationConfiguration(...),
    pipeline_configuration=AddPowerPointPresentationPipelineConfiguration(...),
)

wf = CreatePresentationFromTemplateWorkflow(cfg)

result = wf.create_presentation(
    CreatePresentationFromTemplateWorkflowParameters(
        presentation_name="my_deck",
        template_path="templates/base_template.pptx",
        slides_data=[
            {
                "template_slide_number": 0,
                "shapes": [{"shape_id": "Title 1", "text": "New Title"}],
                "sources": ["https://example.com/source1"],
            }
        ],
    )
)

print(result["download_url"])
```

Using as a LangChain tool:

```python
tool = CreatePresentationFromTemplateWorkflow(cfg).as_tools()[0]
out = tool.run({
    "presentation_name": "my_deck",
    "template_path": "templates/base_template.pptx",
    "slides_data": [],
})
```

## Caveats
- `slides_data` items **must** include `template_slide_number`; otherwise that slide is skipped (logged as error).
- Shape updates and notes updates are wrapped in `try/except`; failures are logged and processing continues.
- `as_api()` does not expose any FastAPI routes (no API endpoint is created here).
- `workspace_id` and `storage_name` default from `ABIModule` configuration; the workflow assumes `ABIModule` is initialized and provides an object storage service.
