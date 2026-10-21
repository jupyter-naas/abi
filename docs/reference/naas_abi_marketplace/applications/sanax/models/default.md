# `default` (Sanax Model Selector)

## What it is
- A small module that selects and exposes a `ChatModel` instance for the Sanax application based on the global `ai_mode` configuration.
- Chooses between an "airgap" model (Qwen) and a cloud model (GPT).

## Public API
- `model: ChatModel`
  - The selected chat model instance to use elsewhere in the application.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.sanax.ABIModule` (via `get_instance()`)
  - `ABIModule.get_instance().configuration.global_config.ai_mode` (string)
  - `naas_abi_core.models.Model.ChatModel` (type annotation)
- Selection logic:
  - If `ai_mode == "airgap"`:
    - Uses `naas_abi_marketplace.ai.qwen.models.qwen3_8b.model`
  - Otherwise:
    - Uses `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`

## Usage
```python
from naas_abi_marketplace.applications.sanax.models.default import model

print(model)          # selected model instance
print(type(model))    # should be compatible with ChatModel
```

## Caveats
- Import-time behavior:
  - `ai_mode` is read and the corresponding model is imported when this module is imported.
- Mode matching:
  - Only the exact string `"airgap"` selects the Qwen model; any other value falls back to the GPT model.
