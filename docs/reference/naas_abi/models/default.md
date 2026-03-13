# `default` (Model Selector)

## What it is
- A small utility module that selects and returns the default `ChatModel` to use based on runtime configuration and availability of an OpenAI API key.

## Public API
- `get_model() -> ChatModel`
  - Returns a `ChatModel` instance:
    - Uses the **airgapped** Qwen model when `ai_mode == "airgap"` **or** when no OpenAI API key is configured.
    - Otherwise uses the **cloud** ChatGPT model (`gpt_4_1_mini`).

## Configuration/Dependencies
- Reads configuration via:
  - `ABIModule.get_instance().configuration.global_config.ai_mode` (`"cloud" | "local" | "airgap"`)
  - `naas_abi_marketplace.ai.chatgpt.ABIModule.get_instance().configuration.openai_api_key`
- Imports models lazily (at call time):
  - `naas_abi.models.airgap_qwen.model`
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`

## Usage
```python
from naas_abi.models.default import get_model

model = get_model()
print(type(model))
```

## Caveats
- If `ai_mode` is not `"airgap"` but the OpenAI API key is missing/empty, the function will still force the airgapped model.
- Selection depends on `ABIModule.get_instance()` being properly initialized and configured at runtime.
