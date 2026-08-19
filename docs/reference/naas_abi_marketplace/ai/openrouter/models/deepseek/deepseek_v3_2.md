# DeepseekV32Model

## What it is
- Defines a `ModelDefinition` for the **DeepSeek V3.2** chat model served via **OpenRouter**.
- Exposes a ready-to-use `ChatModel` instance configured with `langchain_openai.ChatOpenAI`.

## Public API
- `class DeepseekV32Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.DEEPSEEK_V3_2`
  - `MODEL_ID`: `"deepseek/deepseek-v3.2"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Wraps a `ChatOpenAI` client configured with:
      - `model="deepseek/deepseek-v3.2"`
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key` from `ABIModule.get_instance().configuration.openrouter_api_key` (stored as `pydantic.SecretStr`)
- `model: ChatModel`
  - Module-level alias to `DeepseekV32Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set to a valid OpenRouter API key.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.deepseek.deepseek_v3_2 import model

# `model.model` is the underlying ChatOpenAI client.
# Use it as supported by langchain_openai's ChatOpenAI.
client = model.model

# Example (method names depend on your langchain_openai version):
# response = client.invoke("Hello from DeepSeek V3.2 via OpenRouter")
# print(response)
```

## Caveats
- The OpenRouter API key is retrieved at import time via `ABIModule.get_instance()`. If configuration is missing/invalid, import or initialization may fail.
