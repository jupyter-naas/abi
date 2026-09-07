# ImageGenerationStorageWorkflow

## What it is
A workflow that:
- Calls Google Imagen (via Google Generative Language API) to generate an image from a text prompt.
- Saves the generated image bytes and a corresponding prompt `.txt` file into object storage under a configured datastore path.

## Public API
- **`ImageGenerationStorageWorkflowConfiguration` (dataclass)**
  - Configuration values:
    - `gemini_api_key`: API key (defaults from `ABIModule` configuration)
    - `datastore_path`: base datastore path (defaults from `ABIModule` configuration)
    - `model`: Imagen model name (default: `imagen-4.0-generate-preview-06-06`)
    - `base_url`: API base URL (default: `https://generativelanguage.googleapis.com/v1beta/models`)

- **`ImageGenerationStorageWorkflowParameters` (pydantic model)**
  - Inputs:
    - `prompt` *(str, required)*: text prompt to generate the image
    - `file_name` *(Optional[str], default `"generated_image.png"`)*: output image name; if left as default, a “smart” name is derived from the prompt
    - `folder_name` *(Optional[str], default `"images"`)*: declared but not used by the workflow

- **`ImageGenerationStorageWorkflow` (Workflow)**
  - `generate_image(parameters: ImageGenerationStorageWorkflowParameters) -> dict`
    - Calls `{base_url}/{model}:predict?key={gemini_api_key}` with a JSON payload.
    - Decodes `bytesBase64Encoded` from the first prediction.
    - Stores:
      - image file: `<timestamp>_<file_name>` (ensures an image extension; default naming becomes `<3_prompt_words>.png`)
      - prompt file: same base name with `_prompt.txt`
    - Returns a dict containing `success`, message, file paths, timestamp, and model name.
    - On any error, returns `{"success": False, "message": ..., "error": ...}`.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool` named **`gemini_generate_image`** that calls `generate_image`.
  - `as_api(...) -> None`
    - Present but does not register any routes (no implementation beyond default args handling).

## Configuration/Dependencies
- **External services/libraries**
  - `requests`: used to call the Imagen API endpoint.
  - `naas_abi_core.utils.StorageUtils.StorageUtils`: used to persist image bytes and text to object storage.
  - `ABIModule.get_instance()`: provides:
    - `configuration.gemini_api_key`
    - `configuration.datastore_path`
    - `engine.services.object_storage` for `StorageUtils`

- **Storage location**
  - Files are saved under:
    - `os.path.join(datastore_path, "generate_images")`

- **Imagen request payload (fixed by code)**
  - `instances: [{"prompt": <prompt>}]`
  - `parameters`:
    - `sampleCount: 1`
    - `aspectRatio: "1:1"`
    - `safetyFilterLevel: "block_fewest"`
    - `personGeneration: "allow_adult"`

## Usage
```python
from naas_abi_marketplace.ai.gemini.workflows.ImageGenerationStorageWorkflow import (
    ImageGenerationStorageWorkflow,
    ImageGenerationStorageWorkflowConfiguration,
    ImageGenerationStorageWorkflowParameters,
)

cfg = ImageGenerationStorageWorkflowConfiguration()
wf = ImageGenerationStorageWorkflow(cfg)

result = wf.generate_image(
    ImageGenerationStorageWorkflowParameters(
        prompt="A beautiful sunset over mountains with a lake reflection",
        file_name="sunset.png",
    )
)

print(result)
```

## Caveats
- `folder_name` is defined in parameters but is not used when constructing the storage path.
- If `file_name` is left as the default `"generated_image.png"`, the workflow derives a filename from up to the first 3 alphabetic prompt words (length ≥ 3) and forces `.png`.
- For non-200 API responses, the workflow may raise user-friendly errors for some 400 cases (safety/policy or political-figure-related text), but ultimately returns `success: False` with the error string.
