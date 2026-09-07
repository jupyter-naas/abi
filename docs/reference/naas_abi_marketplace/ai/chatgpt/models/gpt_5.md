# Gpt5Model

## What it is
A `ModelDefinition` that preconfigures a `ChatModel` wrapper for OpenAI’s `gpt-5` using `langchain_openai.ChatOpenAI`, with the API key sourced from `ABIModule` configuration.

## Public API
- **Class: `Gpt5Model(ModelDefinition)`**
  - `CANONICAL_ID = CanonicalModelId.GPT_5`: Canonical identifier.
  - `MODEL_ID = "gpt-5"`: OpenAI model name passed to the client.
  - `PROVIDER = ModelProvider.OPENAI`: Provider enum value.
  - `model: ChatModel`: Prebuilt `ChatModel` instance configured with:
    - `model_id="gpt-5"`
    - `provider=ModelProvider.OPENAI`
    - underlying `ChatOpenAI(model="gpt-5", temperature=0, api_key=SecretStr(...))`

- **Module variable: `model: ChatModel`**
  - Alias to `Gpt5Model.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`

- **Required configuration**
  - `ABIModule.get_instance().configuration.openai_api_key` must be set; used to build `SecretStr(...)` for `ChatOpenAI(api_key=...)`.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_5 import model

print(model.model_id)   # "gpt-5"
print(model.provider)   # ModelProvider.OPENAI
```

## Caveats
- The `ChatModel` is instantiated at import time; if `openai_api_key` is missing/invalid, importing this module may fail.
