# `default` (model selector)

## What it is
- A small helper module that selects and returns the default `ChatModel` implementation based on runtime configuration and OpenAI API key availability.

## Public API
- `get_model() -> ChatModel`
  - Returns a `ChatModel` instance/module:
    - **Airgapped/local path**: returns `naas_abi.models.airgap_qwen.model` when:
      - `ABIModule.get_instance().configuration.global_config.ai_mode == "airgap"`, or
      - the ChatGPT module has no `openai_api_key`.
    - **Cloud path**: otherwise returns `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.ABIModule` for reading `configuration.global_config.ai_mode`.
  - `naas_abi_marketplace.ai.chatgpt.ABIModule` for reading `configuration.openai_api_key`.
  - Model modules:
    - `naas_abi.models.airgap_qwen` (airgap fallback)
    - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini` (cloud model)
- `ai_mode` is expected to be one of: `"cloud" | "local" | "airgap"`.

## Usage
```python
from naas_abi.models.default import get_model

model = get_model()
# model is a ChatModel (implementation depends on configuration)
```

## Caveats
- In `"airgap"` mode, the airgap model is always returned regardless of API key presence.
- If the ChatGPT module is configured without an `openai_api_key`, the airgap model is used even when `ai_mode` is not `"airgap"`.
