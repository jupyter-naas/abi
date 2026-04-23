# ImageGenerationStorageWorkflow

## What it is
A workflow that:
- Calls Google Imagen 4.0 (Preview) to generate an image from a text prompt.
- Saves the generated image bytes and a corresponding prompt `.txt` file into a storage-backed folder under a configured datastore path.

## Public API
- **`ImageGenerationStorageWorkflowConfiguration` (dataclass)**
  - Holds configuration for the workflow:
    - `gemini_api_key`: Gemini API key (default from `ABIModule` configuration)
    - `datastore_path`: base datastore path (default from `ABIModule` configuration)
    - `model`: Imagen model name (default: `imagen-4.0-generate-preview-06-06`)
    - `base_url`: API base URL (default: `https://generativelanguage.googleapis.com/v1beta/models`)

- **`ImageGenerationStorageWorkflowParameters` (pydantic model)**
  - Input parameters:
    - `prompt` *(str, required)*: text prompt used to generate the image
    - `file_name` *(Optional[str], default `"generated_image.png"`)*: output image filename; if left as default, a “smart” name is derived from prompt words
    - `folder_name` *(Optional[str], default `"images"`)*: **declared but not used** in storage path

- **`ImageGenerationStorageWorkflow` (Workflow)**
  - `generate_image(parameters) -> dict`
    - Calls Imagen `:predict`, decodes returned base64 image bytes, stores:
      - image file: `<timestamp>_<file_name>.png` (or chosen extension)
      - prompt file: `<timestamp>_<file_name>_prompt.txt`
    - Returns a dict with success flag, paths, filenames, timestamp, model, etc.
    - On failure returns `{"success": False, "message": ..., "error": ...}`.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool` named **`gemini_generate_image`** that calls `generate_image`.
  - `as_api(...) -> None`
    - Defined but intentionally does nothing (returns `None`).

## Configuration/Dependencies
- **External services/libraries**
  - `requests`: used to call Google Generative Language API (Imagen).
  - `naas_abi_core.utils.StorageUtils.StorageUtils`: used to save image bytes and text to object storage.
  - `ABIModule.get_instance()`: used to fetch `gemini_api_key`, `datastore_path`, and object storage service.
- **Storage location**
  - Images are stored under:
    - `os.path.join(datastore_path, "generate_images")`
  - Note: `folder_name` parameter is not used when building the folder path.
- **API endpoint format**
  - `POST {base_url}/{model}:predict?key={gemini_api_key}`
  - Payload includes:
    - `instances: [{"prompt": <prompt>}]`
    - `parameters: {"sampleCount": 1, "aspectRatio": "1:1", "safetyFilterLevel": "block_fewest", "personGeneration": "allow_adult"}`

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
- `folder_name` exists in parameters but is not used in the storage path.
- If the API returns non-200 responses or safety/policy blocks, the workflow raises/handles errors and returns `success: False` with an error message.
- Default `file_name="generated_image.png"` triggers “smart naming” derived from up to the first 3 prompt words (letters only, length ≥ 3) and always stores as `.png`.
