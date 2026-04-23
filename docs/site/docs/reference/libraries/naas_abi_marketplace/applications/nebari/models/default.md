# `default` (Nebari model selector)

## What it is
- A small module that selects and exposes a default `ChatModel` instance based on the global `ai_mode` configuration.
- It switches between an “airgap” model and a cloud model at import time.

## Public API
- `model: ChatModel`
  - The selected chat model instance.
  - Resolved at module import based on `ai_mode`.
- `ai_mode`
  - The resolved AI mode string from Nebari’s global configuration.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.nebari.ABIModule` (singleton access to configuration)
  - `naas_abi_core.models.Model.ChatModel` (type)
- Configuration key used:
  - `ABIModule.get_instance().configuration.global_config.ai_mode`
- Model selection:
  - If `ai_mode == "airgap"`:
    - Imports `naas_abi_marketplace.ai.qwen.models.qwen3_8b.model` as the default `model`
  - Otherwise:
    - Imports `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model` as the default `model`

## Usage
```python
from naas_abi_marketplace.applications.nebari.models.default import model

# Use `model` as a ChatModel instance in your application.
# (Exact invocation depends on ChatModel's interface.)
print(type(model))
```

## Caveats
- Selection happens at import time; changing `ai_mode` after import will not automatically update `model` unless the module is reloaded.
- Importing this module triggers imports of the selected backend model module.
