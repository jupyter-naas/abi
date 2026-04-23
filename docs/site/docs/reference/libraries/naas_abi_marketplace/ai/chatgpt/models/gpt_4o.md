# gpt_4o

## What it is
- A module-level definition of a `ChatModel` configured for OpenAI’s `gpt-4o` via `langchain_openai.ChatOpenAI`.
- Intended to be imported and used as a ready-to-use chat model instance.

## Public API
- `ID: str`
  - Model identifier: `"gpt-4o"`.
- `PROVIDER: str`
  - Provider identifier: `"openai"`.
- `model: naas_abi_core.models.Model.ChatModel`
  - Preconfigured `ChatModel` wrapping a `ChatOpenAI` instance:
    - `model="gpt-4o"`
    - `temperature=0`
    - `api_key` sourced from `ABIModule.get_instance().configuration.openai_api_key` (wrapped as `pydantic.SecretStr`)

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule` for configuration access
  - `pydantic.SecretStr`
- Required configuration:
  - `ABIModule.get_instance().configuration.openai_api_key` must be set to a valid OpenAI API key.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.gpt_4o import model

# `model` is a ChatModel that wraps a LangChain ChatOpenAI client.
# How you call it depends on the ChatModel interface in naas_abi_core.
print(model.model_id, model.provider)
```

## Caveats
- Importing this module will instantiate `ChatOpenAI` immediately and read the OpenAI API key from `ABIModule` configuration. If configuration is missing or not initialized, import-time errors may occur.
