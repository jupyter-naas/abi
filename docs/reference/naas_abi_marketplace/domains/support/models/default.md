# `get_model`

## What it is
A small selector function that returns a `ChatModel` implementation based on the current ABI Marketplace configuration (AI mode and OpenAI API key availability).

## Public API
- `get_model() -> ChatModel`
  - Chooses and returns a chat model:
    - Returns the **airgap** model when:
      - `ai_mode` is `"airgap"`, **or**
      - the ChatGPT module has no `openai_api_key`.
    - Otherwise returns the **cloud** ChatGPT model (`gpt_4_1_mini`).

## Configuration/Dependencies
- Reads configuration from:
  - `naas_abi_marketplace.domains.support.ABIModule.get_instance().configuration.global_config.ai_mode`
    - Expected values: `"cloud" | "local" | "airgap"` (typed as `Literal`).
  - `naas_abi_marketplace.ai.chatgpt.ABIModule.get_instance().configuration.openai_api_key`
- Dynamically imports one of:
  - `naas_abi.models.airgap_qwen.model` (airgapped fallback)
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model` (cloud)

## Usage
```python
from naas_abi_marketplace.domains.support.models.default import get_model

model = get_model()  # returns a ChatModel instance/module-level model
# Use `model` according to the ChatModel interface expected by your runtime.
```

## Caveats
- Selection depends on runtime configuration; in particular:
  - Missing/empty `openai_api_key` forces the airgap model, even if `ai_mode` is not `"airgap"`.
- Imports happen inside the function; import errors can occur at call time if optional dependencies are unavailable.
