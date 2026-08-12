# Gpt41Model

## What it is
- Defines a `gpt-4.1` chat model configuration for use in `naas_abi_marketplace`.
- Wraps a `langchain_openai.ChatOpenAI` instance inside `naas_abi_core.models.Model.ChatModel`.
- Exposes a module-level `model` alias for convenient import.

## Public API
- `class Gpt41Model(ModelDefinition)`
  - `CANONICAL_ID = CanonicalModelId.GPT_4_1`
  - `MODEL_ID = "gpt-4.1"`
  - `PROVIDER = ModelProvider.OPENAI`
  - `model: ChatModel`
    - Preconfigured `ChatModel`:
      - `model_id="gpt-4.1"`
      - `provider=ModelProvider.OPENAI`
      - `model=ChatOpenAI(model="gpt-4.1", temperature=0, timeout=180, max_retries=3, api_key=SecretStr(...))`
- `model: ChatModel`
  - Module-level alias: `Gpt41Model.model`

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model`: `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- Configuration source:
  - OpenAI API key is read at import time from:
    - `ABIModule.get_instance().configuration.openai_api_key`
  - Wrapped as `SecretStr` and passed to `ChatOpenAI(api_key=...)`

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

print(model.model_id)   # "gpt-4.1"
print(model.provider)   # ModelProvider.OPENAI
```

## Caveats
- The `ChatModel` is instantiated at import time; importing this module requires `ABIModule.get_instance().configuration.openai_api_key` to be available.
