# `default` (Nebari default chat model selector)

## What it is
- A small module that exposes a default `ChatModel` instance based on Nebari’s global `ai_mode` configuration.
- Selects an “airgap” model vs. a cloud model at import time.

## Public API
- `model: ChatModel`
  - The selected chat model instance.
  - Resolved when the module is imported.
- `ai_mode`
  - The resolved AI mode string from `ABIModule` global configuration.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.nebari.ABIModule` (access to configuration singleton)
  - `naas_abi_core.models.Model.ChatModel` (type annotation)
- Configuration key:
  - `ABIModule.get_instance().configuration.global_config.ai_mode`
- Selection logic:
  - If `ai_mode == "airgap"`:
    - Uses `naas_abi_marketplace.ai.qwen.models.qwen3_8b.model`
  - Otherwise:
    - Uses `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model`

## Usage
```python
from naas_abi_marketplace.applications.nebari.models.default import model, ai_mode

print("ai_mode:", ai_mode)
print("model type:", type(model))
```

## Caveats
- Model selection happens at import time; changing `ai_mode` after import will not update `model` unless the module is reloaded.
- Importing this module triggers an import of the selected backend model module.
