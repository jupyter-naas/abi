# `default` (Sanax Model Selector)

## What it is
- A small module that selects and exposes a `ChatModel` instance for the Sanax application based on the global `ai_mode` configuration.
- Chooses between an "airgap" model (Qwen) and a cloud model (GPT).

## Public API
- `model: ChatModel`
  - The selected chat model instance to use elsewhere in the application.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.sanax.ABIModule` (singleton access via `get_instance()`)
  - `ABIModule.get_instance().configuration.global_config.ai_mode` (string)
  - `naas_abi_core.models.Model.ChatModel` (type)
- Model selection:
  - If `ai_mode == "airgap"`:
    - Imports `naas_abi_marketplace.ai.qwen.models.qwen3_8b.model` as the selected model.
  - Otherwise:
    - Imports `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model` as the selected model.

## Usage
```python
from naas_abi_marketplace.applications.sanax.models.default import model

# Use `model` wherever a ChatModel is required.
print(type(model))
```

## Caveats
- Import-time behavior:
  - The configuration (`ai_mode`) is read and the model is imported at module import time.
- Mode matching:
  - Only the exact string `"airgap"` selects the airgap (Qwen) model; all other values fall back to the cloud (GPT) model.
